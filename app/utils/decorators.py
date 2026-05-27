"""
Route decorators: login_required and admin_required.
"""
from functools import wraps
from flask import session, flash, redirect
from database.user_model_simple import is_admin


def login_required(f):
    """Require user to be logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để tiếp tục', 'error')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Require user to be admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để tiếp tục', 'error')
            return redirect('/login')
        if not is_admin(session['user_id']):
            flash('Bạn không có quyền truy cập trang này', 'error')
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function
