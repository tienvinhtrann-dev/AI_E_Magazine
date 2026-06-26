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

# Initialize Database schemas (running once when WSGI process starts)
try:
    print("Azure Startup: Checking and initializing database schemas...")
    from database.db_simple import init_database, test_connection, database_exists, ensure_performance_indexes
    from database.user_model_simple import ensure_google_auth_schema, ensure_token_balance_schema
    from database.magazine_model_simple import ensure_magazines_schema
    from database.schedule_model_simple import create_schedules_table
    from database.system_model import init_settings_table
    from database.plan_model import init_plans_tables
    from database.sepay_model import init_sepay_table

    if test_connection():
        print("Azure Startup: Database connection successful!")
    else:
        if database_exists():
            print("Azure Startup: ⚠️ Database connection failed but database exists — skipping init.")
        else:
            print("Azure Startup: Database does not exist. Initializing...")
            init_database()

    ensure_magazines_schema()
    ensure_google_auth_schema()
    ensure_token_balance_schema()
    create_schedules_table()
    init_settings_table()
    init_plans_tables()
    init_sepay_table()
    ensure_performance_indexes()
    print("Azure Startup: Database schemas initialized successfully!")
except Exception as e:
    print(f"Azure Startup Error: Failed to initialize database: {e}")

if __name__ == "__main__":
    app.run()