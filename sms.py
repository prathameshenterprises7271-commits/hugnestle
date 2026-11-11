import requests
from config import Config
from database import get_db

def send_sms(phone: str, message: str, order_id: int = None) -> dict:
    """Dispatches SMS via configured provider and records log into SQLite"""
    provider = Config.SMS_PROVIDER.lower()
    status = "SENT"
    error_msg = None
    
    # Clean phone number (strip whitespace and common prefixes)
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    
    if provider == "twilio" and Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{Config.TWILIO_ACCOUNT_SID}/Messages.json"
            resp = requests.post(
                url,
                auth=(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN),
                data={
                    "From": Config.TWILIO_PHONE_NUMBER,
                    "To": clean_phone if clean_phone.startswith("+") else f"+91{clean_phone}",
                    "Body": message
                },
                timeout=10
            )
            if resp.status_code in (200, 201):
                status = "DELIVERED"
            else:
                status = "FAILED"
                error_msg = resp.text
        except Exception as e:
            status = "FAILED"
            error_msg = str(e)
            
    elif provider == "fast2sms" and Config.FAST2SMS_API_KEY:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {"authorization": Config.FAST2SMS_API_KEY}
            payload = {
                "route": "q",
                "message": message,
                "language": "english",
                "flash": 0,
                "numbers": clean_phone[-10:]
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                status = "DELIVERED"
            else:
                status = "FAILED"
                error_msg = resp.text
        except Exception as e:
            status = "FAILED"
            error_msg = str(e)
            
    else:
        # MOCK / Test mode (Standard default for local and demo environments)
        status = "DELIVERED (SIMULATED)"
        provider = "MOCK_SMS_GATEWAY"
        print(f"\n[📱 SMS SENT TO {clean_phone}]:\n{message}\n")

    # Store in database log
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO sms_logs (order_id, phone, message, status, provider)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, clean_phone, message, status, provider))
    except Exception as e:
        print(f"[Database SMS Log Error]: {e}")
        
    return {"success": status.startswith("DELIVERED") or status == "SENT", "status": status, "error": error_msg}

def send_order_confirmation_sms(order: dict):
    """Sends order confirmation SMS to customer"""
    customer_name = order.get("customer_name", "Friend")
    order_num = order.get("order_number", "")
    total = order.get("total_amount", 0.0)
    phone = order.get("customer_phone", "")
    
    msg = (
        f"🧸 HUGNESTLE: Yay {customer_name}! Your cute order #{order_num} is CONFIRMED! "
        f"Amount: ₹{total:,.2f} paid via UPI. We're hand-packing your plushies with love. "
        f"Track your package: /track?order={order_num}&phone={phone}"
    )
    return send_sms(phone=phone, message=msg, order_id=order.get("id"))

def send_order_status_update_sms(order: dict, new_status: str):
    """Sends SMS notification when order tracking status changes"""
    customer_name = order.get("customer_name", "Friend")
    order_num = order.get("order_number", "")
    phone = order.get("customer_phone", "")
    
    status_text_map = {
        "CONFIRMED": "is confirmed and queued for packing!",
        "PACKING": "is being wrapped with ribbons & cuddly love! 🎀",
        "DISPATCHED": f"has been dispatched via {order.get('courier_name', 'BlueDart')} (Tracking: {order.get('tracking_number', 'HUG-TRK-8819')})! 🚀",
        "OUT_FOR_DELIVERY": "is OUT FOR DELIVERY today! Keep your arms ready for hugs! 📦✨",
        "DELIVERED": "has been DELIVERED! We hope it brings endless smiles and warm hugs! 💖🧸"
    }
    
    status_desc = status_text_map.get(new_status, f"status updated to {new_status}")
    msg = f"🧸 HUGNESTLE: Hey {customer_name}, your order #{order_num} {status_desc} Track: /track?order={order_num}&phone={phone}"
    return send_sms(phone=phone, message=msg, order_id=order.get("id"))
