"""
Authentication routes: register, login, Google OAuth, logout.
"""
import secrets
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlencode

import requests as http_requests
from flask import session, flash, redirect, url_for, render_template, request
from dotenv import load_dotenv

from app import config
from app.utils.decorators import login_required
from database.user_model_simple import (
    create_user, verify_user, sync_google_user,
    get_user_by_email, update_password_by_email, update_password_by_user_id,
    update_password_hash_by_email,
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


def _get_google_redirect_uri():
    """Quyết định redirect_uri động nếu truy cập qua ngrok để tránh lỗi mất cookie session."""
    from urllib.parse import urlparse
    proto = request.headers.get('X-Forwarded-Proto', request.scheme)
    host = request.headers.get('X-Forwarded-Host', request.host)
    if config.GOOGLE_REDIRECT_URI:
        parsed = urlparse(config.GOOGLE_REDIRECT_URI)
        if parsed.netloc == host:
            return config.GOOGLE_REDIRECT_URI
    return f"{proto}://{host}/auth/google/callback"



def _redirect_after_login(user):
    """Redirect user after successful login (same flow as original)."""
    user_mags = get_magazines_by_user(user['id'])
    if not user_mags:
        return redirect(url_for('create_magazine_page'))
    return redirect("/dashboard?tab=stats")


def _send_password_email(to_email, temp_password):
    """Gửi mật khẩu tạm thời qua Gmail SMTP."""
    load_dotenv(dotenv_path=getattr(config, "ENV_PATH", None), override=True)
    smtp_user = (os.getenv('MAIL_USERNAME') or getattr(config, 'MAIL_USERNAME', '') or '').strip()
    smtp_pass = (os.getenv('MAIL_PASSWORD') or getattr(config, 'MAIL_PASSWORD', '') or '').strip()
    smtp_host = (os.getenv('MAIL_SERVER') or getattr(config, 'MAIL_SERVER', '') or 'smtp.gmail.com').strip()
    smtp_port = int((os.getenv('MAIL_PORT') or getattr(config, 'MAIL_PORT', 587) or 587))
    use_tls = str(os.getenv('MAIL_USE_TLS') or getattr(config, 'MAIL_USE_TLS', '1')).strip() not in ('0', 'false', 'False')
    from_name = (os.getenv('MAIL_FROM_NAME') or getattr(config, 'MAIL_FROM_NAME', '') or 'AI E-Magazine').strip()
    from_email = (os.getenv('MAIL_FROM_EMAIL') or getattr(config, 'MAIL_FROM_EMAIL', '') or smtp_user).strip()

    if not smtp_user or not smtp_pass:
        raise RuntimeError("Thiếu MAIL_USERNAME hoặc MAIL_PASSWORD trong .env")

    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg["Subject"] = "Khoi phuc mat khau - AI E-Magazine"

    body = (
        "Xin chao,\n\n"
        "He thong da tao mat khau tam thoi cho tai khoan cua ban.\n\n"
        f"Mat khau tam thoi: {temp_password}\n\n"
        "Vui long dang nhap bang mat khau tam thoi nay, sau do vao trang DOI MAT KHAU de dat mat khau moi de nho hon.\n"
        f"Link dang nhap: {config.APP_BASE_URL}/login\n\n"
        "Neu ban khong yeu cau thao tac nay, vui long bo qua email.\n\n"
        "Tran trong,\n"
        "AI E-Magazine"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())


def _mail_config_ready():
    load_dotenv(dotenv_path=getattr(config, "ENV_PATH", None), override=True)
    smtp_user = (os.getenv('MAIL_USERNAME') or getattr(config, 'MAIL_USERNAME', '') or '').strip()
    smtp_pass = (os.getenv('MAIL_PASSWORD') or getattr(config, 'MAIL_PASSWORD', '') or '').strip()
    if not (smtp_user and smtp_pass):
        return False
    # Guard against placeholder values in template .env files.
    placeholders = ("your_gmail", "example", "changeme")
    combined = f"{smtp_user} {smtp_pass}".lower()
    return not any(marker in combined for marker in placeholders)


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

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            if not email:
                flash("Vui lòng nhập email.", "error")
                return render_template("forgot_password.html")
            user = get_user_by_email(email)
            if not user:
                flash("Email không tồn tại trong hệ thống.", "error")
                return render_template("forgot_password.html")
            if user.get("is_active", 1) == 0:
                flash("Tài khoản đã bị khóa. Vui lòng liên hệ admin.", "error")
                return render_template("forgot_password.html")
            if not _mail_config_ready():
                flash("Hệ thống chưa cấu hình MAIL_USERNAME/MAIL_PASSWORD trong .env nên chưa thể gửi email.", "error")
                return render_template("forgot_password.html")

            temp_password = secrets.token_urlsafe(8)
            old_password_hash = user.get("password")
            ok = update_password_by_email(email, temp_password)
            if not ok:
                flash("Không thể đặt lại mật khẩu. Vui lòng thử lại.", "error")
                return render_template("forgot_password.html")
            try:
                _send_password_email(email, temp_password)
                flash("Mật khẩu tạm thời đã được gửi về email của bạn.", "success")
                return redirect(url_for("login"))
            except Exception as exc:
                print(f"❌ Forgot password mail error: {exc}")
                if old_password_hash:
                    update_password_hash_by_email(email, old_password_hash)
                err = str(exc)
                if "535" in err or "BadCredentials" in err or "Username and Password not accepted" in err:
                    flash(
                        "Gửi email thất bại: Gmail từ chối đăng nhập SMTP. "
                        "Hãy dùng đúng MAIL_USERNAME và Gmail App Password 16 ký tự trong .env.",
                        "error",
                    )
                else:
                    flash(
                        "Gửi email thất bại nên hệ thống đã khôi phục mật khẩu cũ. "
                        "Vui lòng kiểm tra cấu hình mail.",
                        "error",
                    )
                return render_template("forgot_password.html")
        return render_template("forgot_password.html")

    @app.route("/change-password", methods=["GET", "POST"])
    @login_required
    def change_password():
        if request.method == "POST":
            old_password = request.form.get("old_password") or ""
            new_password = request.form.get("new_password") or ""
            confirm_password = request.form.get("confirm_password") or ""

            if not old_password or not new_password or not confirm_password:
                flash("Vui lòng nhập đầy đủ thông tin.", "error")
                return render_template("change_password.html")
            if len(new_password) < 6:
                flash("Mật khẩu mới cần ít nhất 6 ký tự.", "error")
                return render_template("change_password.html")
            if new_password != confirm_password:
                flash("Xác nhận mật khẩu không khớp.", "error")
                return render_template("change_password.html")

            current_user = verify_user(session.get("user_email"), old_password)
            if not current_user:
                flash("Mật khẩu hiện tại không đúng.", "error")
                return render_template("change_password.html")

            ok = update_password_by_user_id(session.get("user_id"), new_password)
            if not ok:
                flash("Đổi mật khẩu thất bại, vui lòng thử lại.", "error")
                return render_template("change_password.html")

            flash("Đổi mật khẩu thành công.", "success")
            return redirect("/dashboard?tab=stats")
        return render_template("change_password.html")

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
        redirect_uri = _get_google_redirect_uri()
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
        redirect_uri = _get_google_redirect_uri()
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
