"""
Authentication routes: register, login, Google OAuth, logout.
"""
import secrets
from urllib.parse import urlencode

import requests as http_requests
from flask import session, flash, redirect, url_for, render_template, request

from app import config
from app.utils.decorators import login_required
from database.user_model_simple import (
    create_user, verify_user, sync_google_user,
)
from database.magazine_model_simple import get_magazines_by_user


# ------------------------------------------------------------------
# Local helpers
# ------------------------------------------------------------------

def _google_oauth_enabled():
    if not (config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET):
        return False
    placeholder_markers = (
        "your-google-client-id",
        "your-google-client-secret",
        "changeme",
        "example",
    )
    cid  = config.GOOGLE_CLIENT_ID.lower()
    csec = config.GOOGLE_CLIENT_SECRET.lower()
    return not any(marker in cid or marker in csec for marker in placeholder_markers)


def _redirect_after_login(user):
    """Redirect user after successful login (same flow as original)."""
    user_mags = get_magazines_by_user(user['id'])
    if not user_mags:
        return redirect(url_for('create_magazine_page'))
    return redirect("/dashboard?tab=stats")


# ------------------------------------------------------------------
# Route registration
# ------------------------------------------------------------------

def register_routes(app):

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            email     = request.form.get("email")
            password  = request.form.get("password")
            full_name = request.form.get("full_name")
            if not email or not password:
                flash("Vui lòng điền đầy đủ thông tin", "error")
                return render_template("register.html")
            user_id = create_user(email, password, 'user', full_name)
            if user_id:
                flash("Đăng ký thành công! Vui lòng đăng nhập để tiếp tục.", "success")
                return redirect(url_for('login'))
            else:
                flash("Email đã tồn tại!", "error")
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email    = request.form.get("email")
            password = request.form.get("password")
            user = verify_user(email, password)
            if user and 'error' not in user:
                session['user_id']    = user['id']
                session['user_email'] = user['email']
                session['user_role']  = user['role']
                session['full_name']  = user['full_name']
                user_mags = get_magazines_by_user(user['id'])
                if not user_mags:
                    return redirect(url_for('create_magazine_page'))
                return redirect("/dashboard?tab=stats")
            elif user and user.get('error') == 'locked':
                flash("Tài khoản của bạn đã bị khóa. Vui lòng liên hệ admin!", "error")
            else:
                flash("Email hoặc mật khẩu không đúng!", "error")
        return render_template("login.html")

    @app.route("/auth/google")
    def google_login():
        if not _google_oauth_enabled():
            flash(
                "Google login chưa cấu hình đúng. Vui lòng cập nhật GOOGLE_CLIENT_ID và "
                "GOOGLE_CLIENT_SECRET trong file .env.",
                "error",
            )
            return redirect(url_for('login'))
        state = secrets.token_urlsafe(32)
        session['google_oauth_state'] = state
        redirect_uri = config.GOOGLE_REDIRECT_URI or url_for('google_callback', _external=True)
        params = {
            'client_id':     config.GOOGLE_CLIENT_ID,
            'redirect_uri':  redirect_uri,
            'response_type': 'code',
            'scope':         'openid email profile',
            'state':         state,
            'access_type':   'online',
            'prompt':        'select_account',
        }
        return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")

    @app.route("/auth/google/callback")
    def google_callback():
        if not _google_oauth_enabled():
            flash(
                "Google login chưa cấu hình đúng. Vui lòng cập nhật GOOGLE_CLIENT_ID và "
                "GOOGLE_CLIENT_SECRET trong file .env.",
                "error",
            )
            return redirect(url_for('login'))
        if request.args.get('error'):
            flash("Đăng nhập Google đã bị hủy hoặc gặp lỗi.", "error")
            return redirect(url_for('login'))
        state = request.args.get('state')
        if not state or state != session.get('google_oauth_state'):
            flash("Phiên đăng nhập Google không hợp lệ. Vui lòng thử lại.", "error")
            return redirect(url_for('login'))
        code = request.args.get('code')
        if not code:
            flash("Không nhận được mã xác thực từ Google.", "error")
            return redirect(url_for('login'))
        redirect_uri = config.GOOGLE_REDIRECT_URI or url_for('google_callback', _external=True)
        try:
            token_response = http_requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    'code':          code,
                    'client_id':     config.GOOGLE_CLIENT_ID,
                    'client_secret': config.GOOGLE_CLIENT_SECRET,
                    'redirect_uri':  redirect_uri,
                    'grant_type':    'authorization_code',
                },
                timeout=15,
            )
            token_response.raise_for_status()
            token_data   = token_response.json()
            access_token = token_data.get('access_token')
            if not access_token:
                raise ValueError('Missing access_token')
            profile_response = http_requests.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=15,
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
            if not profile.get('email'):
                flash("Google không trả về email tài khoản.", "error")
                return redirect(url_for('login'))
            if profile.get('email_verified') is False:
                flash("Email Google chưa được xác minh.", "error")
                return redirect(url_for('login'))
            user = sync_google_user(
                email=profile.get('email'),
                full_name=profile.get('name') or profile.get('given_name'),
                google_id=profile.get('sub'),
            )
            if not user:
                flash("Không thể tạo tài khoản Google trong hệ thống.", "error")
                return redirect(url_for('login'))
            if user.get('is_active', 1) == 0:
                flash("Tài khoản của bạn đã bị khóa. Vui lòng liên hệ admin!", "error")
                return redirect(url_for('login'))
            session['user_id']    = user['id']
            session['user_email'] = user['email']
            session['user_role']  = user.get('role', 'user')
            session['full_name']  = user.get('full_name')
            session['avatar_url'] = profile.get('picture') or ''
            session.pop('google_oauth_state', None)
            return _redirect_after_login(user)
        except http_requests.RequestException as exc:
            print(f"❌ Google OAuth error: {exc}")
            flash("Không thể xác thực với Google lúc này. Vui lòng thử lại.", "error")
            return redirect(url_for('login'))
        except Exception as exc:
            print(f"❌ Google OAuth unexpected error: {exc}")
            flash("Đăng nhập Google thất bại.", "error")
            return redirect(url_for('login'))

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect("/")
