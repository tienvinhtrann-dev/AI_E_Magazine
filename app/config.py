"""
Application Configuration
Loads environment variables and defines app-level constants.
"""
import os
from dotenv import load_dotenv

# Base directory of the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Always load .env from project root (independent of current working directory)
load_dotenv(dotenv_path=ENV_PATH, override=True)


def _env(name: str, default: str = "") -> str:
    """Read env var and normalize optional wrapping quotes/spaces."""
    value = os.getenv(name, default)
    return str(value).strip().strip('"').strip("'")

# Flask
SECRET_KEY = "ai_e_magazine_v2_secret_key_2026"

# Google OAuth
GOOGLE_CLIENT_ID     = _env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _env("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = _env("GOOGLE_REDIRECT_URI")

# SePay
SEPAY_API_KEY        = _env("SEPAY_API_KEY")
SEPAY_WEBHOOK_SECRET = _env("SEPAY_WEBHOOK_SECRET")
SEPAY_BANK_BIN       = _env("SEPAY_BANK_BIN", "970418")
SEPAY_BANK_NAME      = _env("SEPAY_BANK_NAME", "BIDV")
SEPAY_ACCOUNT_NO     = _env("SEPAY_ACCOUNT_NO")
SEPAY_ACCOUNT_NAME   = _env("SEPAY_ACCOUNT_NAME")
SEPAY_QR_TEMPLATE    = _env("SEPAY_QR_TEMPLATE", "compact2")
APP_BASE_URL       = _env("APP_BASE_URL", "http://localhost:5000").rstrip("/")

# VNPAY
VNPAY_TMN_CODE     = _env("VNPAY_TMN_CODE")
VNPAY_HASH_SECRET  = _env("VNPAY_HASH_SECRET")
VNPAY_PAYMENT_URL  = _env("VNPAY_PAYMENT_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
VNPAY_RETURN_URL   = _env("VNPAY_RETURN_URL", f"{APP_BASE_URL}/payment/vnpay-return")

# Mail (Forgot password)
MAIL_SERVER    = _env("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT      = int(_env("MAIL_PORT", "587") or "587")
MAIL_USE_TLS   = _env("MAIL_USE_TLS", "1")
MAIL_USERNAME  = _env("MAIL_USERNAME") or _env("MAIL_USER")
MAIL_PASSWORD  = _env("MAIL_PASSWORD") or _env("MAIL_PASS")
MAIL_FROM_NAME = _env("MAIL_FROM_NAME", "AI E-Magazine")
MAIL_FROM_EMAIL = _env("MAIL_FROM_EMAIL")

# Debug prints (same as original)
print('GOOGLE_CLIENT_ID:', GOOGLE_CLIENT_ID)
print('GOOGLE_CLIENT_SECRET:', GOOGLE_CLIENT_SECRET)
print('GOOGLE_REDIRECT_URI:', GOOGLE_REDIRECT_URI)
print(f'[SEPAY] ACCOUNT_NO={SEPAY_ACCOUNT_NO[-4:] if SEPAY_ACCOUNT_NO else "MISSING"}')
print(f'[VNPAY] TMN={"SET" if VNPAY_TMN_CODE else "MISSING"}')
print(f'[MAIL] USER={"SET" if MAIL_USERNAME else "MISSING"}, PASS={"SET" if MAIL_PASSWORD else "MISSING"}')
