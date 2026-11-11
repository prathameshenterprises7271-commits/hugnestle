import hmac
import hashlib
import json
import uuid
import requests
from config import Config
from database import get_db
from sms import send_order_confirmation_sms

def generate_upi_link(order_number: str, amount: float, store_name: str = None, upi_id: str = None) -> str:
    """Generate standard NPCI UPI Intent URI for payment apps & QR codes"""
    name = (store_name or Config.STORE_NAME).replace(" ", "%20")
    pa = upi_id or Config.STORE_UPI_ID
    am = f"{amount:.2f}"
    tr = order_number
    tn = f"Hugnestle%20Plushie%20Order%20{order_number}".replace(" ", "%20")
    return f"upi://pay?pa={pa}&pn={name}&am={am}&tr={tr}&tn={tn}&cu=INR"

def create_payment_order(order_number: str, amount: float):
    """
    Creates payment order payload.
    If real Razorpay API keys are configured and live, attempts official Razorpay API call.
    Otherwise, operates in safe Test / Sandbox UPI mode.
    """
    amount_in_paise = int(round(amount * 100))
    
    if Config.PAYMENT_MODE == "live" and Config.RAZORPAY_KEY_ID and not Config.RAZORPAY_KEY_ID.startswith("rzp_test_hugnestle"):
        try:
            resp = requests.post(
                "https://api.razorpay.com/v1/orders",
                auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET),
                json={
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "receipt": order_number,
                    "notes": {"brand": "Hugnestle", "order_number": order_number}
                },
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "mode": "live",
                    "key_id": Config.RAZORPAY_KEY_ID,
                    "razorpay_order_id": data["id"],
                    "amount": amount,
                    "amount_paise": amount_in_paise,
                    "upi_link": generate_upi_link(order_number, amount)
                }
        except Exception as e:
            print(f"[Razorpay API Error]: {e}")
            
    # Test Mode / Sandbox UPI Order
    test_order_id = f"order_hug_test_{uuid.uuid4().hex[:12]}"
    upi_link = generate_upi_link(order_number, amount)
    
    return {
        "success": True,
        "mode": "test",
        "key_id": Config.RAZORPAY_KEY_ID,
        "razorpay_order_id": test_order_id,
        "amount": amount,
        "amount_paise": amount_in_paise,
        "upi_link": upi_link,
        "upi_id": Config.STORE_UPI_ID,
        "test_instructions": "UPI Test Sandbox Mode: scan QR code or choose test UPI simulator to verify instantly."
    }

def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, signature: str) -> bool:
    """Verifies HMAC SHA-256 signature for Razorpay / UPI response"""
    if not razorpay_order_id or not razorpay_payment_id:
        return False
        
    # In test mode with test orders
    if razorpay_order_id.startswith("order_hug_test_"):
        # Valid test signature check
        expected = hmac.new(
            Config.RAZORPAY_KEY_SECRET.encode("utf-8"),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        # In test sandbox, accept valid HMAC or demo test prefix
        if signature == expected or signature.startswith("sig_test_") or signature == "test_verified_signature":
            return True

    # Real Razorpay signature verification
    msg = f"{razorpay_order_id}|{razorpay_payment_id}"
    generated_sig = hmac.new(
        Config.RAZORPAY_KEY_SECRET.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(generated_sig, signature)

def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verifies Razorpay Webhook signature"""
    if not signature_header or not Config.RAZORPAY_WEBHOOK_SECRET:
        return False
    computed = hmac.new(
        Config.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature_header)

def confirm_payment_and_deduct_stock(order_number: str, payment_id: str, upi_txn_id: str = None) -> dict:
    """
    Atomically:
    1. Checks if order is already confirmed
    2. Verifies stock availability
    3. Decreases product stock
    4. Logs stock changes
    5. Marks order as 'VERIFIED' and 'CONFIRMED'
    6. Dispatches SMS confirmation
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Fetch order
        order = cursor.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()
        if not order:
            return {"success": False, "message": "Order not found"}
            
        if order["payment_status"] == "VERIFIED":
            return {"success": True, "message": "Order is already confirmed", "order": order}
            
        # 2. Fetch order items
        items = cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],)).fetchall()
        
        # 3. Check and deduct stock atomically
        for item in items:
            prod_id = item["product_id"]
            qty = item["quantity"]
            if prod_id:
                prod = cursor.execute("SELECT id, name, stock FROM products WHERE id = ?", (prod_id,)).fetchone()
                if prod:
                    current_stock = prod["stock"]
                    if current_stock < qty:
                        return {
                            "success": False,
                            "message": f"Sorry! Item '{prod['name']}' only has {current_stock} in stock, but order requested {qty}."
                        }
                    new_stock = max(0, current_stock - qty)
                    cursor.execute("UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_stock, prod_id))
                    cursor.execute("""
                        INSERT INTO stock_logs (product_id, change_amount, previous_stock, new_stock, reason)
                        VALUES (?, ?, ?, ?, ?)
                    """, (prod_id, -qty, current_stock, new_stock, f"Order {order_number} verified UPI payment"))

        # 4. Mark order as VERIFIED
        txn_ref = upi_txn_id or f"UPI-{uuid.uuid4().hex[:10].upper()}"
        cursor.execute("""
            UPDATE orders 
            SET payment_status = 'VERIFIED',
                fulfillment_status = 'CONFIRMED',
                upi_txn_id = ?,
                razorpay_payment_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (txn_ref, payment_id, order["id"]))
        
        # Reload order
        updated_order = cursor.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()
        
    # 5. Dispatch customer order confirmation SMS (outside DB lock)
    try:
        send_order_confirmation_sms(updated_order)
    except Exception as e:
        print(f"[SMS Dispatch Error]: {e}")
        
    return {"success": True, "message": "Payment verified and stock updated successfully!", "order": updated_order}
