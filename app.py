"""
AI E-Magazine - Entry Point
Delegates app creation to app/ package, handles startup initialization.
"""
import sys
# Fix UnicodeEncodeError with emoji/Vietnamese on Windows console
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load environment variables FIRST before any app imports
from dotenv import load_dotenv
load_dotenv(override=True)

# ── App factory ───────────────────────────────────────────────────
from app import create_app
from app.extensions import scheduler, article_generator  # noqa: F401 (used at startup)
from app.services.scheduler_service import _load_all_schedules, start_sepay_poll_job

# ── Database helpers needed at startup ───────────────────────────
from database.db_simple import init_database, test_connection, database_exists, ensure_performance_indexes
from database.user_model_simple import ensure_google_auth_schema, ensure_token_balance_schema
from database.magazine_model_simple import ensure_magazines_schema
from database.schedule_model_simple import create_schedules_table
from database.system_model import init_settings_table
from database.plan_model import init_plans_tables
from database.sepay_model import init_sepay_table

import atexit

# Create the Flask application
app = create_app()


# ----------------------------------
# Initialize & Run
# ----------------------------------

if __name__ == "__main__":
    import os
    print("=" * 70)
    print("  AI E-MAGAZINE - SIMPLIFIED VERSION")
    print("=" * 70)
    print("\n  Initializing...")

    if test_connection():
        print("  Database connected!")
    else:
        if database_exists():
            print("  ⚠️  Kết nối thất bại nhưng database đã tồn tại — bỏ qua init.")
        else:
            print("  Database chưa tồn tại. Đang khởi tạo...")
            init_database()

    ensure_magazines_schema()
    ensure_google_auth_schema()
    ensure_token_balance_schema()
    create_schedules_table()
    init_settings_table()
    init_plans_tables()
    init_sepay_table()
    ensure_performance_indexes()

    # Chỉ khởi động scheduler trong worker process (tránh start 2 lần với reloader)
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        if not scheduler.running:
            scheduler.start()
            _load_all_schedules()
            start_sepay_poll_job()
            atexit.register(lambda: scheduler.shutdown(wait=False))
            print("  Scheduler started!")

    print("\n  URL: http://127.0.0.1:5000")
    print("=" * 70)

    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=True)
