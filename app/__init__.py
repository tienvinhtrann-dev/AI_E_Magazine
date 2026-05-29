"""
Flask application factory.
Creates and configures the Flask app, registers all routes.
"""
import os
import json as _json
from datetime import datetime
from flask import Flask, session, request

from app import config


def create_app():
    """Create and return the configured Flask application."""
    # Resolve paths relative to the project root (two levels up from this file)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, 'templates'),
        static_folder=os.path.join(project_root, 'static'),
    )
    app.secret_key = config.SECRET_KEY

    # ------------------------------------------------------------------
    # Sync user role from DB on every request (catches admin promotions)
    # ------------------------------------------------------------------

    @app.before_request
    def refresh_user_role():
        if 'user_id' not in session:
            return
        from database.user_model_simple import get_user_by_id
        user = get_user_by_id(session['user_id'])
        if user and user.get('role') != session.get('user_role'):
            session['user_role'] = user['role']

    # Simple request logger to help debug mobile API calls
    @app.before_request
    def _log_request_debug():
        try:
            import sys
            sys.stdout.write(f"[REQ] {request.method} {request.path}\n")
            if request.method == 'POST' and request.path == '/api/auth/google':
                try:
                    data = request.get_data(as_text=True)
                    sys.stdout.write(f"[REQ-BODY] {data}\n")
                except Exception:
                    pass
            sys.stdout.flush()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Context processors
    # ------------------------------------------------------------------

    @app.context_processor
    def inject_current_date():
        try:
            now = datetime.now()
            return {
                "current_date":     now,
                "current_date_str": now.strftime("%d/%m/%Y"),
            }
        except Exception:
            return {"current_date": None, "current_date_str": ""}

    # ------------------------------------------------------------------
    # Template filters
    # ------------------------------------------------------------------

    @app.template_filter('fromjson')
    def fromjson_filter(value):
        if not value:
            return []
        try:
            return _json.loads(value)
        except Exception:
            return []

    @app.template_filter('slugify')
    def slugify_filter(value):
        from app.utils.helpers import _slugify
        return _slugify(value)

    # ------------------------------------------------------------------
    # Register all route modules
    # ------------------------------------------------------------------

    from app.routes import auth, public, dashboard, magazine, article, admin, payment, api

    auth.register_routes(app)
    public.register_routes(app)
    dashboard.register_routes(app)
    magazine.register_routes(app)
    article.register_routes(app)
    admin.register_routes(app)
    payment.register_routes(app)
    api.register_routes(app)

    # Bypass localtunnel browser warning for webhook requests
    @app.after_request
    def add_localtunnel_bypass(response):
        response.headers["Bypass-Tunnel-Reminder"] = "true"
        return response

    return app
