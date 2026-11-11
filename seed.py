import sqlite3
from config import Config
from database import init_db, get_db
from auth import hash_password

def seed_database():
    print("🌱 Initializing database schema...")
    init_db()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Seed Admin User
        admin_email = "admin@hugnestle.in"
        existing_admin = cursor.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
        if not existing_admin:
            admin_pwd_hash = hash_password(Config.ADMIN_PASSWORD)
            cursor.execute("""
                INSERT INTO users (name, email, phone, password_hash, role, address, city, state, pincode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("Hugnestle Admin Owner", admin_email, "9880011223", admin_pwd_hash, "admin", "Hugnestle HQ, Blossom Avenue", "Bengaluru", "Karnataka", "560001"))
            print(f"✅ Admin user created: {admin_email} / {Config.ADMIN_PASSWORD}")
            
        # 2. Seed Demo Customer User
        cust_email = "priya@example.com"
        existing_cust = cursor.execute("SELECT id FROM users WHERE email = ?", (cust_email,)).fetchone()
        if not existing_cust:
            cust_pwd_hash = hash_password("password123")
            cursor.execute("""
                INSERT INTO users (name, email, phone, password_hash, role, address, city, state, pincode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("Priya Sharma", cust_email, "9876543210", cust_pwd_hash, "customer", "Flat 402, Rosewood Blossom Apts, Indiranagar", "Bengaluru", "Karnataka", "560038"))
            print(f"✅ Customer user created: {cust_email} / password123")

        # 3. Seed Categories
        categories_data = [
            ("Teddy Bears", "teddy-bears", "🧸", "Classic cuddly soft teddy bears with love."),
            ("Giant Plushies", "giant-plushies", "✨", "Full size huggable companions for cozy nights."),
            ("Cute Animals", "cute-animals", "🐼", "Pandas, bunnies, penguins and lovable friends."),
            ("Gift Combos", "gift-combos", "🎁", "Gift-ready hampers with ribbon, chocolates & fairy lights."),
            ("Cushions & Pillows", "cushions-pillows", "🥑", "Super-soft hug cushions for beds, couches and chairs.")
        ]
        
        cat_map = {}
        for name, slug, icon, desc in categories_data:
            existing = cursor.execute("SELECT id FROM categories WHERE slug = ?", (slug,)).fetchone()
            if not existing:
                cursor.execute("""
                    INSERT INTO categories (name, slug, icon, description)
                    VALUES (?, ?, ?, ?)
                """, (name, slug, icon, desc))
                cat_id = cursor.lastrowid
            else:
                cat_id = existing["id"]
            cat_map[slug] = cat_id
            
        print(f"✅ Seeded {len(cat_map)} categories.")

        # 4. Seed Demo Products
        # Note: We give one product stock = 0 to demonstrate the "Out of Stock" feature required by prompt!
        products = [
            {
                "name": "Caramel Teddy Hug Bear",
                "slug": "caramel-teddy-hug-bear",
                "category_slug": "teddy-bears",
                "description": "Our signature Caramel Teddy Bear is crafted from cloud-like velvet microfiber. Stuffed with hypoallergenic micro-pearl cotton, it gives the warmest, coziest embrace. Features an elegant burgundy neck bow and stitched paw details.",
                "price": 899.0,
                "original_price": 1299.0,
                "stock": 14,
                "main_image": "/static/uploads/products/caramel_teddy.svg",
                "dimensions": "45 cm x 30 cm",
                "material": "100% Anti-Allergic Micro-Velvet",
                "tag": "Bestseller",
                "rating": 4.9,
                "review_count": 48,
                "is_featured": 1,
                "extra_images": [
                    "/static/uploads/products/caramel_teddy.svg",
                    "/static/uploads/products/blush_pink_bear.svg"
                ]
            },
            {
                "name": "Blush Pink Cuddle Bear",
                "slug": "blush-pink-cuddle-bear",
                "category_slug": "teddy-bears",
                "description": "Dressed in lovely pastel strawberry cream tones, this adorable bear brings sweet comfort to any room. Perfect gift for birthdays, anniversaries, and cheer-up moments.",
                "price": 949.0,
                "original_price": 1399.0,
                "stock": 8,
                "main_image": "/static/uploads/products/blush_pink_bear.svg",
                "dimensions": "42 cm x 28 cm",
                "material": "Ultra-Fluffy Rosette Plush",
                "tag": "Cute Pick",
                "rating": 5.0,
                "review_count": 36,
                "is_featured": 1,
                "extra_images": [
                    "/static/uploads/products/blush_pink_bear.svg",
                    "/static/uploads/products/caramel_teddy.svg"
                ]
            },
            {
                "name": "Boba Bobo Panda Plush",
                "slug": "boba-bobo-panda-plush",
                "category_slug": "cute-animals",
                "description": "Meet Bobo the chubby panda holding his favorite brown sugar pearl boba milk tea! Extra squishy and soft with sweet embroidered eyes and rosy cheeks.",
                "price": 799.0,
                "original_price": 1199.0,
                "stock": 20,
                "main_image": "/static/uploads/products/bobo_panda.svg",
                "dimensions": "38 cm x 26 cm",
                "material": "Down Cotton & Spandex Soft Pile",
                "tag": "Trending",
                "rating": 4.8,
                "review_count": 29,
                "is_featured": 1,
                "extra_images": [
                    "/static/uploads/products/bobo_panda.svg"
                ]
            },
            {
                "name": "Fluffy Floppy Velvet Bunny",
                "slug": "fluffy-floppy-velvet-bunny",
                "category_slug": "cute-animals",
                "description": "With extra long silky ears and an adorable strawberry hairpin, this floppy bunny will steal your heart. Incredibly light and tender to cuddle.",
                "price": 849.0,
                "original_price": 1249.0,
                "stock": 12,
                "main_image": "/static/uploads/products/floppy_bunny.svg",
                "dimensions": "48 cm (including ears) x 22 cm",
                "material": "Silky Feather Cotton",
                "tag": "New Arrival",
                "rating": 4.9,
                "review_count": 19,
                "is_featured": 1,
                "extra_images": [
                    "/static/uploads/products/floppy_bunny.svg"
                ]
            },
            {
                "name": "Grand Romantic Hug Combo",
                "slug": "grand-romantic-hug-combo",
                "category_slug": "gift-combos",
                "description": "The ultimate gift surprise box! Includes a premium Hugnestle plush bear tucked inside a luxury satin-ribboned pastel gift box, warm fairy lights, and a customized handwritten message card.",
                "price": 1799.0,
                "original_price": 2499.0,
                "stock": 6,
                "main_image": "/static/uploads/products/luxury_hug_combo.svg",
                "dimensions": "Box 35cm x 35cm x 40cm",
                "material": "Luxury Plush + Keepsake Gift Box + LED Lights",
                "tag": "Gift Combo",
                "rating": 5.0,
                "review_count": 52,
                "is_featured": 1,
                "extra_images": [
                    "/static/uploads/products/luxury_hug_combo.svg",
                    "/static/uploads/products/caramel_teddy.svg"
                ]
            },
            {
                "name": "Smiling Avocado Hug Cushion",
                "slug": "smiling-avocado-hug-cushion",
                "category_slug": "cushions-pillows",
                "description": "Ergonomic, plump and irresistibly happy! This cute avocado cushion doubles as cozy lumbar support for your work desk and a bedtime hug pillow.",
                "price": 699.0,
                "original_price": 999.0,
                "stock": 16,
                "main_image": "/static/uploads/products/avocado_hug.svg",
                "dimensions": "45 cm x 35 cm",
                "material": "Elastic Soft Plush + High Rebound PP Cotton",
                "tag": "Cozy Cushion",
                "rating": 4.7,
                "review_count": 22,
                "is_featured": 0,
                "extra_images": [
                    "/static/uploads/products/avocado_hug.svg"
                ]
            },
            {
                "name": "Chilly Chubby Scarf Penguin",
                "slug": "chilly-chubby-scarf-penguin",
                "category_slug": "cute-animals",
                "description": "Round as a snowball with a warm pastel pink knitted scarf. His chubby tummy and soft orange flippers make him the sweetest winter cuddle buddy.",
                "price": 749.0,
                "original_price": 1099.0,
                "stock": 10,
                "main_image": "/static/uploads/products/chubby_penguin.svg",
                "dimensions": "35 cm x 30 cm",
                "material": "Velboa Soft Plush + Knitted Wool Scarf",
                "tag": "Limited Edition",
                "rating": 4.9,
                "review_count": 14,
                "is_featured": 0,
                "extra_images": [
                    "/static/uploads/products/chubby_penguin.svg"
                ]
            },
            {
                "name": "Giant 100cm Fluffy Papa Bear",
                "slug": "giant-100cm-fluffy-papa-bear",
                "category_slug": "giant-plushies",
                "description": "A massive, life-sized 100cm teddy bear! Crafted for giant, full-body embraces. High-density rebound stuffing ensures he stays fluffy and never flattens over time. (Currently out of stock due to massive holiday demand — restock coming soon!)",
                "price": 2499.0,
                "original_price": 3499.0,
                "stock": 0,  # Demonstrates OUT OF STOCK requirement
                "main_image": "/static/uploads/products/giant_cuddle_bear.svg",
                "dimensions": "100 cm x 65 cm",
                "material": "Premium Thick Down Fiber Cotton",
                "tag": "Giant Hug",
                "rating": 5.0,
                "review_count": 64,
                "is_featured": 1,
                "extra_images": [
                    "/static/uploads/products/giant_cuddle_bear.svg"
                ]
            }
        ]

        for p in products:
            existing_p = cursor.execute("SELECT id FROM products WHERE slug = ?", (p["slug"],)).fetchone()
            cat_id = cat_map.get(p["category_slug"])
            if not existing_p:
                cursor.execute("""
                    INSERT INTO products (name, slug, category_id, description, price, original_price, stock, main_image, dimensions, material, tag, rating, review_count, is_featured)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p["name"], p["slug"], cat_id, p["description"], p["price"], p["original_price"],
                    p["stock"], p["main_image"], p["dimensions"], p["material"], p["tag"],
                    p["rating"], p["review_count"], p["is_featured"]
                ))
                p_id = cursor.lastrowid
                
                # Insert extra gallery images
                for idx, img_url in enumerate(p["extra_images"]):
                    cursor.execute("""
                        INSERT INTO product_images (product_id, image_url, sort_order)
                        VALUES (?, ?, ?)
                    """, (p_id, img_url, idx))
            else:
                p_id = existing_p["id"]

        print(f"✅ Seeded {len(products)} products (including in-stock & out-of-stock items).")

        # 5. Seed a demo completed order for testing customer history & tracking
        cust = cursor.execute("SELECT id FROM users WHERE email = ?", (cust_email,)).fetchone()
        if cust:
            demo_order_num = "HUG-202611-9284"
            existing_order = cursor.execute("SELECT id FROM orders WHERE order_number = ?", (demo_order_num,)).fetchone()
            if not existing_order:
                cursor.execute("""
                    INSERT INTO orders (
                        order_number, user_id, customer_name, customer_phone, customer_email,
                        shipping_address, city, state, pincode, subtotal, discount, shipping_fee,
                        total_amount, payment_status, payment_method, upi_txn_id, razorpay_payment_id,
                        fulfillment_status, courier_name, tracking_number, estimated_delivery, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    demo_order_num, cust["id"], "Priya Sharma", "9876543210", cust_email,
                    "Flat 402, Rosewood Blossom Apts, Indiranagar", "Bengaluru", "Karnataka", "560038",
                    899.0, 0.0, 0.0, 899.0, "VERIFIED", "UPI", "UPI-HUG-TXN8829", "pay_test_8829314",
                    "DISPATCHED", "BlueDart Cute Express", "BD-HUG-9912048", "Tomorrow by 4:00 PM",
                    "Please pack with extra pink ribbon and a cute birthday note!"
                ))
                order_id = cursor.lastrowid
                
                # Order Item
                cursor.execute("""
                    INSERT INTO order_items (order_id, product_id, product_name, product_image, price, quantity, total)
                    VALUES (?, 1, 'Caramel Teddy Hug Bear', '/static/uploads/products/caramel_teddy.svg', 899.0, 1, 899.0)
                """, (order_id,))
                
                # Sample SMS Log
                cursor.execute("""
                    INSERT INTO sms_logs (order_id, phone, message, status, provider)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    order_id, "9876543210",
                    "🧸 HUGNESTLE: Yay Priya Sharma! Your cute order #HUG-202611-9284 is CONFIRMED! Amount: ₹899.00 paid via UPI. We are hand-packing your plushies with love. Track your package: /track?order=HUG-202611-9284&phone=9876543210",
                    "DELIVERED (SIMULATED)", "MOCK_SMS_GATEWAY"
                ))
                print(f"✅ Demo order {demo_order_num} seeded for customer {cust_email}.")

    print("🎉 Database seeded successfully!")

if __name__ == "__main__":
    seed_database()
