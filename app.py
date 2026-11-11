import os
import re
import uuid
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort, send_from_directory
)
from werkzeug.utils import secure_filename

from config import Config
from database import get_db, init_db
from auth import (
    hash_password, verify_password, get_current_user,
    admin_required, customer_required
)
from payments import (
    create_payment_order, verify_payment_signature,
    verify_webhook_signature, confirm_payment_and_deduct_stock
)
from sms import send_sms, send_order_status_update_sms

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directory exists
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def generate_slug(name):
    base_slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name).strip().lower()
    base_slug = re.sub(r'[\s-]+', '-', base_slug)
    return f"{base_slug}-{uuid.uuid4().hex[:6]}"

@app.context_processor
def inject_global_context():
    """Inject current user, store settings, and helper utilities into templates"""
    user = get_current_user()
    is_admin = session.get('is_admin', False)
    return {
        'current_user': user,
        'is_admin': is_admin,
        'STORE_NAME': Config.STORE_NAME,
        'STORE_UPI_ID': Config.STORE_UPI_ID,
        'PAYMENT_MODE': Config.PAYMENT_MODE,
        'now_year': datetime.now().year
    }

# ===================================================
# CUSTOMER FRONTEND ROUTES
# ===================================================

@app.route('/')
def index():
    """Homepage: Hero, Categories, Bestsellers, Value Propositions, Reviews"""
    with get_db() as conn:
        categories = conn.execute("SELECT * FROM categories ORDER BY id ASC").fetchall()
        featured_products = conn.execute("""
            SELECT p.*, c.name as category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_featured = 1
            ORDER BY p.id ASC LIMIT 8
        """).fetchall()
        bestsellers = conn.execute("""
            SELECT p.*, c.name as category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.stock DESC LIMIT 4
        """).fetchall()
        
    return render_template('index.html',
                           categories=categories,
                           featured_products=featured_products,
                           bestsellers=bestsellers)

@app.route('/shop')
def shop():
    """Product Catalog with Search, Category Filter, Price & Stock Filters, and Sorting"""
    category_slug = request.args.get('cat', '').strip()
    search_query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'featured').strip()
    in_stock_only = request.args.get('in_stock', '').strip() == '1'
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)

    query = """
        SELECT p.*, c.name as category_name, c.slug as category_slug
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    """
    params = []

    if category_slug:
        query += " AND c.slug = ?"
        params.append(category_slug)

    if search_query:
        query += " AND (p.name LIKE ? OR p.description LIKE ? OR p.tag LIKE ?)"
        wildcard = f"%{search_query}%"
        params.extend([wildcard, wildcard, wildcard])

    if in_stock_only:
        query += " AND p.stock > 0"

    if min_price is not None:
        query += " AND p.price >= ?"
        params.append(min_price)

    if max_price is not None:
        query += " AND p.price <= ?"
        params.append(max_price)

    if sort_by == 'price_asc':
        query += " ORDER BY p.price ASC"
    elif sort_by == 'price_desc':
        query += " ORDER BY p.price DESC"
    elif sort_by == 'newest':
        query += " ORDER BY p.id DESC"
    elif sort_by == 'popular':
        query += " ORDER BY p.review_count DESC"
    else:
        query += " ORDER BY p.is_featured DESC, p.id ASC"

    with get_db() as conn:
        products = conn.execute(query, params).fetchall()
        categories = conn.execute("SELECT * FROM categories ORDER BY name ASC").fetchall()

    return render_template('shop.html',
                           products=products,
                           categories=categories,
                           selected_category=category_slug,
                           search_query=search_query,
                           sort_by=sort_by,
                           in_stock_only=in_stock_only,
                           min_price=min_price,
                           max_price=max_price)

@app.route('/product/<slug>')
def product_detail(slug):
    """Product Detail Page with multiple images, specifications, stock indicator"""
    with get_db() as conn:
        product = conn.execute("""
            SELECT p.*, c.name as category_name, c.slug as category_slug
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.slug = ?
        """, (slug,)).fetchone()

        if not product:
            abort(404)

        images = conn.execute("""
            SELECT image_url FROM product_images 
            WHERE product_id = ? ORDER BY sort_order ASC
        """, (product['id'],)).fetchall()
        
        gallery = [img['image_url'] for img in images]
        if product['main_image'] not in gallery:
            gallery.insert(0, product['main_image'])

        related_products = conn.execute("""
            SELECT * FROM products 
            WHERE category_id = ? AND id != ?
            LIMIT 4
        """, (product['category_id'], product['id'])).fetchall()

    return render_template('product.html',
                           product=product,
                           gallery=gallery,
                           related_products=related_products)

@app.route('/checkout')
def checkout():
    """Checkout Page with UPI Payment integration and No Cash on Delivery notice"""
    user = get_current_user()
    return render_template('checkout.html', user=user)

# ===================================================
# CHECKOUT & PAYMENT API (UPI / RAZORPAY / WEBHOOK)
# ===================================================

@app.route('/api/checkout/create-order', methods=['POST'])
def api_create_order():
    """
    Validates stock for all cart items, creates an order in PENDING status,
    and returns UPI payment payload with dynamic QR code instructions.
    """
    data = request.get_json() or {}
    items = data.get('items', [])
    customer = data.get('customer', {})
    
    if not items:
        return jsonify({'success': False, 'message': 'Your shopping cart is empty!'}), 400

    name = customer.get('name', '').strip()
    phone = customer.get('phone', '').strip()
    email = customer.get('email', '').strip()
    address = customer.get('address', '').strip()
    city = customer.get('city', '').strip()
    state = customer.get('state', '').strip()
    pincode = customer.get('pincode', '').strip()
    notes = customer.get('notes', '').strip()

    if not all([name, phone, address, city, pincode]):
        return jsonify({'success': False, 'message': 'Please provide complete delivery details (Name, Phone, Address, City, Pincode).'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Validate items and verify stock availability
        subtotal = 0.0
        verified_items = []
        
        for item in items:
            prod_id = item.get('id')
            req_qty = int(item.get('quantity', 1))
            if req_qty <= 0:
                continue

            product = cursor.execute("SELECT * FROM products WHERE id = ?", (prod_id,)).fetchone()
            if not product:
                return jsonify({'success': False, 'message': f'Product ID {prod_id} is no longer available.'}), 400

            if product['stock'] < req_qty:
                return jsonify({
                    'success': False,
                    'message': f"Sorry! '{product['name']}' only has {product['stock']} units left in stock. Please adjust your cart quantity."
                }), 400

            item_total = product['price'] * req_qty
            subtotal += item_total
            verified_items.append({
                'product_id': product['id'],
                'product_name': product['name'],
                'product_image': product['main_image'],
                'price': product['price'],
                'quantity': req_qty,
                'total': item_total
            })

        if not verified_items:
            return jsonify({'success': False, 'message': 'No valid products in cart.'}), 400

        # Calculate discount or shipping
        discount = 0.0
        shipping_fee = 0.0  # Free shipping promotion for Hugnestle
        total_amount = subtotal - discount + shipping_fee

        # 2. Generate unique Order Number (e.g. HUG-202611-38291)
        order_number = f"HUG-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        user_id = session.get('user_id')

        cursor.execute("""
            INSERT INTO orders (
                order_number, user_id, customer_name, customer_phone, customer_email,
                shipping_address, city, state, pincode, subtotal, discount, shipping_fee,
                total_amount, payment_status, payment_method, fulfillment_status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 'UPI', 'CONFIRMED', ?)
        """, (
            order_number, user_id, name, phone, email,
            address, city, state, pincode, subtotal, discount, shipping_fee,
            total_amount, notes
        ))
        order_id = cursor.lastrowid

        # Insert Order Items
        for vi in verified_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, product_image, price, quantity, total)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id, vi['product_id'], vi['product_name'], vi['product_image'], vi['price'], vi['quantity'], vi['total']))

    # 3. Create UPI / Razorpay payment payload
    payment_data = create_payment_order(order_number, total_amount)

    return jsonify({
        'success': True,
        'order_number': order_number,
        'order_id': order_id,
        'total_amount': total_amount,
        'payment': payment_data
    })

@app.route('/api/payments/verify', methods=['POST'])
def api_verify_payment():
    """
    Verifies payment signature from frontend UPI/Razorpay flow.
    Upon verification, atomically deducts stock and confirms order.
    """
    data = request.get_json() or {}
    order_number = data.get('order_number')
    payment_id = data.get('razorpay_payment_id') or data.get('payment_id')
    order_id = data.get('razorpay_order_id') or data.get('order_id')
    signature = data.get('razorpay_signature') or data.get('signature', 'sig_test_verified')
    upi_txn_id = data.get('upi_txn_id')

    if not order_number or not payment_id:
        return jsonify({'success': False, 'message': 'Missing order number or payment identifier.'}), 400

    # Verify signature
    is_valid = verify_payment_signature(order_id, payment_id, signature)
    if not is_valid:
        return jsonify({'success': False, 'message': 'Security check failed: Invalid payment signature!'}), 400

    # Atomically reduce stock, mark order verified, dispatch SMS
    result = confirm_payment_and_deduct_stock(order_number, payment_id, upi_txn_id)
    if not result.get('success'):
        return jsonify({'success': False, 'message': result.get('message', 'Stock allocation failed.')}), 400

    return jsonify({
        'success': True,
        'message': 'Payment successfully verified!',
        'redirect_url': url_for('order_success', order_number=order_number)
    })

@app.route('/api/payments/webhook', methods=['POST'])
def api_payments_webhook():
    """
    Payment gateway webhook endpoint (e.g. Razorpay webhook)
    Verifies HMAC signature and processes payment.captured event
    """
    signature = request.headers.get('X-Razorpay-Signature', '')
    raw_body = request.get_data()

    if Config.PAYMENT_MODE == 'live':
        if not verify_webhook_signature(raw_body, signature):
            return jsonify({'status': 'rejected', 'reason': 'Invalid webhook signature'}), 400

    try:
        payload = request.get_json()
        event = payload.get('event')
        if event in ('payment.captured', 'order.paid'):
            entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
            notes = entity.get('notes', {})
            order_number = notes.get('order_number')
            payment_id = entity.get('id')
            upi_ref = entity.get('vpa') or entity.get('acquirer_data', {}).get('upi_transaction_id')
            if order_number and payment_id:
                confirm_payment_and_deduct_stock(order_number, payment_id, upi_ref)
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        print(f"[Webhook Error]: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/order/success/<order_number>')
def order_success(order_number):
    """Order confirmation page after verified payment with confetti & summary"""
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()
        if not order:
            flash('Order not found.', 'danger')
            return redirect(url_for('index'))

        items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order['id'],)).fetchall()
        sms_log = conn.execute("""
            SELECT * FROM sms_logs WHERE order_id = ? ORDER BY id DESC LIMIT 1
        """, (order['id'],)).fetchone()

    return render_template('order_success.html', order=order, items=items, sms_log=sms_log)

@app.route('/track')
def track_order():
    """Customer Order Tracking with visual progress stepper and SMS history"""
    order_number = request.args.get('order', '').strip()
    phone = request.args.get('phone', '').strip()
    order = None
    items = []
    sms_logs = []

    if order_number:
        with get_db() as conn:
            if phone:
                order = conn.execute("""
                    SELECT * FROM orders 
                    WHERE order_number = ? AND customer_phone LIKE ?
                """, (order_number, f"%{phone[-10:]}%")).fetchone()
            else:
                order = conn.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()

            if order:
                items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order['id'],)).fetchall()
                sms_logs = conn.execute("SELECT * FROM sms_logs WHERE order_id = ? ORDER BY id DESC", (order['id'],)).fetchall()

    return render_template('track.html',
                           order=order,
                           items=items,
                           sms_logs=sms_logs,
                           searched_order=order_number,
                           searched_phone=phone)

# ===================================================
# CUSTOMER AUTHENTICATION & ORDER HISTORY
# ===================================================

@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    """Customer Login and Registration"""
    if session.get('user_id'):
        return redirect(url_for('customer_orders'))

    next_url = request.args.get('next', url_for('customer_orders'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'register':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            phone = request.form.get('phone', '').strip()
            password = request.form.get('password', '')
            address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            pincode = request.form.get('pincode', '').strip()

            if not name or not email or not password:
                flash('Please fill in all required fields (Name, Email, Password).', 'warning')
                return render_template('customer_login.html', active_tab='register', next=next_url)

            with get_db() as conn:
                existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                if existing:
                    flash('An account with this email already exists. Please log in.', 'danger')
                    return render_template('customer_login.html', active_tab='login', next=next_url)

                pwd_hash = hash_password(password)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (name, email, phone, password_hash, role, address, city, pincode)
                    VALUES (?, ?, ?, ?, 'customer', ?, ?, ?)
                """, (name, email, phone, pwd_hash, address, city, pincode))
                user_id = cursor.lastrowid

            session['user_id'] = user_id
            session['user_name'] = name
            session['user_email'] = email
            flash(f'Welcome to Hugnestle, {name}! Your cute account has been created.', 'success')
            return redirect(next_url)

        elif action == 'login':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')

            with get_db() as conn:
                user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

            if user and verify_password(password, user['password_hash']):
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_email'] = user['email']
                if user['role'] == 'admin':
                    session['is_admin'] = True
                flash(f'Welcome back, {user["name"]}! 💕', 'success')
                return redirect(next_url)
            else:
                flash('Invalid email or password. Please try again.', 'danger')
                return render_template('customer_login.html', active_tab='login', next=next_url)

    return render_template('customer_login.html', active_tab='login', next=next_url)

@app.route('/customer/logout')
def customer_logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('index'))

@app.route('/customer/orders')
@customer_required
def customer_orders():
    """Customer account dashboard showing their past orders"""
    user_id = session.get('user_id')
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        orders = conn.execute("""
            SELECT * FROM orders 
            WHERE user_id = ? OR customer_email = ?
            ORDER BY id DESC
        """, (user_id, user['email'])).fetchall()
        
        # Attach order items to each order
        orders_with_items = []
        for o in orders:
            items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (o['id'],)).fetchall()
            orders_with_items.append({'order': o, 'order_items': items})

    return render_template('customer_orders.html', user=user, orders_with_items=orders_with_items)

# ===================================================
# ADMIN PANEL (SECURE AUTH, CRUD, STOCK, ORDERS)
# ===================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Dedicated secure admin login for website owner"""
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # 1. Check against master admin config
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session['is_admin'] = True
            session['admin_user'] = username
            flash('Welcome to your Hugnestle Admin Panel!', 'success')
            return redirect(url_for('admin_dashboard'))

        # 2. Check against admin users in database
        with get_db() as conn:
            admin_user = conn.execute("SELECT * FROM users WHERE (email = ? OR name = ?) AND role = 'admin'", (username, username)).fetchone()
            if admin_user and verify_password(password, admin_user['password_hash']):
                session['is_admin'] = True
                session['admin_user'] = admin_user['name']
                session['user_id'] = admin_user['id']
                flash('Welcome to your Hugnestle Admin Panel!', 'success')
                return redirect(url_for('admin_dashboard'))

        flash('Invalid admin credentials. Access restricted to store owner only.', 'danger')

    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_user', None)
    flash('Admin session signed out successfully.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_root():
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin Dashboard: Metrics, Low Stock Alerts, Recent Orders"""
    with get_db() as conn:
        total_orders = conn.execute("SELECT COUNT(*) as count FROM orders").fetchone()['count']
        total_revenue = conn.execute("SELECT COALESCE(SUM(total_amount), 0) as total FROM orders WHERE payment_status = 'VERIFIED'").fetchone()['total']
        total_products = conn.execute("SELECT COUNT(*) as count FROM products").fetchone()['count']
        total_stock = conn.execute("SELECT COALESCE(SUM(stock), 0) as total FROM products").fetchone()['total']

        # Low stock products (stock <= 3 or 0)
        low_stock_products = conn.execute("""
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.stock <= 5
            ORDER BY p.stock ASC
        """).fetchall()

        # Recent 8 orders
        recent_orders = conn.execute("""
            SELECT * FROM orders ORDER BY id DESC LIMIT 8
        """).fetchall()

    return render_template('admin/dashboard.html',
                           total_orders=total_orders,
                           total_revenue=total_revenue,
                           total_products=total_products,
                           total_stock=total_stock,
                           low_stock_products=low_stock_products,
                           recent_orders=recent_orders)

@app.route('/admin/products')
@admin_required
def admin_products():
    """Products list with stock adjustments, direct image uploads, edit/delete"""
    with get_db() as conn:
        products = conn.execute("""
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.id DESC
        """).fetchall()
        categories = conn.execute("SELECT * FROM categories ORDER BY name ASC").fetchall()

    return render_template('admin/products.html', products=products, categories=categories)

@app.route('/admin/products/add', methods=['POST'])
@admin_required
def admin_add_product():
    """Add new product with direct file uploads from computer or phone"""
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id', type=int)
    price = request.form.get('price', type=float)
    original_price = request.form.get('original_price', type=float)
    stock = request.form.get('stock', type=int, default=0)
    description = request.form.get('description', '').strip()
    dimensions = request.form.get('dimensions', '').strip()
    material = request.form.get('material', '').strip()
    tag = request.form.get('tag', '').strip()
    is_featured = 1 if request.form.get('is_featured') else 0

    if not name or price is None or stock is None or not description:
        flash('Please provide product name, valid price, initial stock, and description.', 'danger')
        return redirect(url_for('admin_products'))

    slug = generate_slug(name)
    uploaded_image_paths = []

    # Handle file uploads
    files = request.files.getlist('images')
    for f in files:
        if f and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            save_path = os.path.join(Config.UPLOAD_FOLDER, unique_name)
            f.save(save_path)
            uploaded_image_paths.append(f"/static/uploads/products/{unique_name}")

    # Fallback image if none uploaded
    if not uploaded_image_paths:
        uploaded_image_paths.append('/static/uploads/products/caramel_teddy.svg')

    main_image = uploaded_image_paths[0]

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (
                name, slug, category_id, description, price, original_price,
                stock, main_image, dimensions, material, tag, is_featured
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, slug, category_id, description, price, original_price,
            stock, main_image, dimensions, material, tag, is_featured
        ))
        prod_id = cursor.lastrowid

        # Insert multiple gallery images
        for idx, img_path in enumerate(uploaded_image_paths):
            cursor.execute("""
                INSERT INTO product_images (product_id, image_url, sort_order)
                VALUES (?, ?, ?)
            """, (prod_id, img_path, idx))

        # Log initial stock
        cursor.execute("""
            INSERT INTO stock_logs (product_id, change_amount, previous_stock, new_stock, reason)
            VALUES (?, ?, 0, ?, 'Initial Product Creation')
        """, (prod_id, stock, stock))

    flash(f"Product '{name}' added successfully with {stock} units in stock!", 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/products/edit/<int:product_id>', methods=['POST'])
@admin_required
def admin_edit_product(product_id):
    """Edit existing product details, price, description, and upload more photos"""
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id', type=int)
    price = request.form.get('price', type=float)
    original_price = request.form.get('original_price', type=float)
    stock = request.form.get('stock', type=int)
    description = request.form.get('description', '').strip()
    dimensions = request.form.get('dimensions', '').strip()
    material = request.form.get('material', '').strip()
    tag = request.form.get('tag', '').strip()
    is_featured = 1 if request.form.get('is_featured') else 0

    with get_db() as conn:
        cursor = conn.cursor()
        product = cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product:
            flash('Product not found.', 'danger')
            return redirect(url_for('admin_products'))

        # Track stock changes
        prev_stock = product['stock']
        if stock != prev_stock:
            cursor.execute("""
                INSERT INTO stock_logs (product_id, change_amount, previous_stock, new_stock, reason)
                VALUES (?, ?, ?, ?, 'Manual Stock Adjustment from Admin Edit')
            """, (product_id, stock - prev_stock, prev_stock, stock))

        # Handle optional new photo uploads
        files = request.files.getlist('images')
        main_img = product['main_image']
        new_photos = []
        for f in files:
            if f and allowed_file(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}.{ext}"
                save_path = os.path.join(Config.UPLOAD_FOLDER, unique_name)
                f.save(save_path)
                photo_url = f"/static/uploads/products/{unique_name}"
                new_photos.append(photo_url)
                cursor.execute("""
                    INSERT INTO product_images (product_id, image_url, sort_order)
                    VALUES (?, ?, 10)
                """, (product_id, photo_url))

        if new_photos and request.form.get('set_main_image'):
            main_img = new_photos[0]

        cursor.execute("""
            UPDATE products 
            SET name = ?, category_id = ?, price = ?, original_price = ?, stock = ?,
                description = ?, dimensions = ?, material = ?, tag = ?, is_featured = ?,
                main_image = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            name, category_id, price, original_price, stock,
            description, dimensions, material, tag, is_featured,
            main_img, product_id
        ))

    flash(f"Product '{name}' updated successfully!", 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    """Delete a product"""
    with get_db() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    flash('Product deleted successfully.', 'info')
    return redirect(url_for('admin_products'))

@app.route('/api/admin/products/<int:product_id>/stock', methods=['POST'])
@admin_required
def api_admin_update_stock(product_id):
    """
    Interactive AJAX stock adjuster: increase/decrease/set stock
    instantly from the admin table without reloading!
    """
    data = request.get_json() or {}
    delta = data.get('delta')
    new_stock_val = data.get('new_stock')

    with get_db() as conn:
        cursor = conn.cursor()
        prod = cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not prod:
            return jsonify({'success': False, 'message': 'Product not found'}), 404

        prev_stock = prod['stock']
        if delta is not None:
            updated_stock = max(0, prev_stock + int(delta))
        elif new_stock_val is not None:
            updated_stock = max(0, int(new_stock_val))
        else:
            return jsonify({'success': False, 'message': 'Invalid stock update payload'}), 400

        change = updated_stock - prev_stock
        cursor.execute("UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (updated_stock, product_id))
        cursor.execute("""
            INSERT INTO stock_logs (product_id, change_amount, previous_stock, new_stock, reason)
            VALUES (?, ?, ?, ?, 'Admin Quick Stock Update')
        """, (product_id, change, prev_stock, updated_stock))

    return jsonify({
        'success': True,
        'product_id': product_id,
        'stock': updated_stock,
        'is_out_of_stock': updated_stock == 0,
        'message': f"Stock updated to {updated_stock}"
    })

@app.route('/admin/orders')
@admin_required
def admin_orders():
    """View and manage all customer orders, payment status, tracking status"""
    status_filter = request.args.get('status', 'ALL').strip().upper()
    search = request.args.get('q', '').strip()

    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if status_filter != 'ALL':
        query += " AND (fulfillment_status = ? OR payment_status = ?)"
        params.extend([status_filter, status_filter])

    if search:
        query += " AND (order_number LIKE ? OR customer_phone LIKE ? OR customer_name LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY id DESC"

    with get_db() as conn:
        orders = conn.execute(query, params).fetchall()
        
        # Attach order items to each order
        orders_with_items = []
        for o in orders:
            items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (o['id'],)).fetchall()
            orders_with_items.append({'order': o, 'order_items': items})

    return render_template('admin/orders.html',
                           orders_with_items=orders_with_items,
                           selected_status=status_filter,
                           search=search)

@app.route('/admin/orders/<int:order_id>/status', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    """
    Update order fulfillment status (CONFIRMED, PACKING, DISPATCHED, OUT_FOR_DELIVERY, DELIVERED)
    and optional courier tracking info. Dispatches status update SMS!
    """
    new_status = request.form.get('fulfillment_status', '').strip().upper()
    courier_name = request.form.get('courier_name', '').strip()
    tracking_number = request.form.get('tracking_number', '').strip()
    send_sms_flag = request.form.get('send_sms_notification') == '1'

    with get_db() as conn:
        cursor = conn.cursor()
        order = cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            flash('Order not found.', 'danger')
            return redirect(url_for('admin_orders'))

        cursor.execute("""
            UPDATE orders 
            SET fulfillment_status = ?,
                courier_name = COALESCE(NULLIF(?, ''), courier_name),
                tracking_number = COALESCE(NULLIF(?, ''), tracking_number),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, courier_name, tracking_number, order_id))

        updated_order = cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

    # Trigger customer notification SMS if requested
    if send_sms_flag:
        send_order_status_update_sms(updated_order, new_status)
        flash(f"Order #{updated_order['order_number']} status changed to {new_status} and customer SMS dispatched!", 'success')
    else:
        flash(f"Order #{updated_order['order_number']} status updated to {new_status}.", 'success')

    return redirect(url_for('admin_orders'))

@app.route('/admin/sms-logs')
@admin_required
def admin_sms_logs():
    """Admin SMS Notification Log Viewer"""
    with get_db() as conn:
        logs = conn.execute("""
            SELECT s.*, o.order_number, o.customer_name
            FROM sms_logs s
            LEFT JOIN orders o ON s.order_id = o.id
            ORDER BY s.id DESC LIMIT 100
        """).fetchall()

    return render_template('admin/sms_logs.html', logs=logs)

# ===================================================
# APPLICATION STARTUP
# ===================================================

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🧸 HUGNESTLE E-COMMERCE SERVER RUNNING")
    print(f"👉 Local URL: http://localhost:{Config.PORT}")
    print(f"👉 Admin Login: http://localhost:{Config.PORT}/admin/login")
    print(f"   Username: {Config.ADMIN_USERNAME}")
    print(f"   Password: {Config.ADMIN_PASSWORD}")
    print(f"👉 Payment Mode: {Config.PAYMENT_MODE.upper()} (UPI QR & App Simulator active)")
    print("=" * 60)
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
