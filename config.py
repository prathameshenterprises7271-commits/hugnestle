import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Simple .env file parser if python-dotenv isn't loaded
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = val

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "hugnestle-default-super-secret-key-2026")
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "t")
    
    # Database & Storage
    IS_VERCEL = bool(os.environ.get("VERCEL"))
    if IS_VERCEL:
        DATABASE_PATH = Path("/tmp") / "hugnestle.db"
        UPLOAD_FOLDER = Path("/tmp") / "uploads" / "products"
    else:
        DATABASE_PATH = BASE_DIR / "hugnestle.db"
        UPLOAD_FOLDER = BASE_DIR / "static" / "uploads" / "products"

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
    
    # Admin Credentials
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "hugnestle@admin2026")
    
    # UPI & Payments
    PAYMENT_MODE = os.environ.get("PAYMENT_MODE", "test")  # 'test' or 'live'
    STORE_NAME = os.environ.get("STORE_NAME", "HUGNESTLE")
    STORE_UPI_ID = os.environ.get("STORE_UPI_ID", "pay.hugnestle@okhdfcbank")
    
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_hugnestle12345")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "secret_hugnestle_test_key_98765")
    RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "webhook_secret_hugnestle_2026")
    
    # SMS
    SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "mock")
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
    FAST2SMS_API_KEY = os.environ.get("FAST2SMS_API_KEY", "")
