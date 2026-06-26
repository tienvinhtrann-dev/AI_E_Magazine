"""
WSGI entry point for Azure App Service / Gunicorn
"""

import sys

# Fix Unicode
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

# Create Flask application
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()