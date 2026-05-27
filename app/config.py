"""
Application Configuration
Loads environment variables and defines app-level constants.
"""
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Base directory of the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Flask
SECRET_KEY = "ai_e_magazine_v2_secret_key_2026"

# Google OAuth
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "").strip()

# SePay
SEPAY_API_KEY        = os.getenv("SEPAY_API_KEY", "").strip()
SEPAY_WEBHOOK_SECRET = os.getenv("SEPAY_WEBHOOK_SECRET", "").strip()
SEPAY_BANK_BIN       = os.getenv("SEPAY_BANK_BIN", "970418").strip()
SEPAY_BANK_NAME      = os.getenv("SEPAY_BANK_NAME", "BIDV").strip()
SEPAY_ACCOUNT_NO     = os.getenv("SEPAY_ACCOUNT_NO", "").strip()
SEPAY_ACCOUNT_NAME   = os.getenv("SEPAY_ACCOUNT_NAME", "").strip()
SEPAY_QR_TEMPLATE    = os.getenv("SEPAY_QR_TEMPLATE", "compact2").strip()
APP_BASE_URL       = os.getenv("APP_BASE_URL", "http://localhost:5000").rstrip("/")

# Debug prints (same as original)
print('GOOGLE_CLIENT_ID:', GOOGLE_CLIENT_ID)
print('GOOGLE_CLIENT_SECRET:', GOOGLE_CLIENT_SECRET)
print('GOOGLE_REDIRECT_URI:', GOOGLE_REDIRECT_URI)
print(f'[SEPAY] ACCOUNT_NO={SEPAY_ACCOUNT_NO[-4:] if SEPAY_ACCOUNT_NO else "MISSING"}')
