import os
import sys
from pathlib import Path

# Add project root directory to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from config import Config
from seed import seed_database

# When running on Vercel serverless, ensure database is initialized & seeded in /tmp
if os.environ.get("VERCEL"):
    if not Config.DATABASE_PATH.exists():
        try:
            Config.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
            seed_database()
        except Exception as e:
            print(f"[Vercel Init Error]: {e}")

# Expose WSGI handler for Vercel
# Vercel's Python runtime expects 'app'
