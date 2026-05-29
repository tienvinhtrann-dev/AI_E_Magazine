"""
Admin routes: panel, users, content, system, plans, subscriptions, backup.
"""
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta

from flask import session, flash, redirect, url_for, render_template, request, jsonify, send_file, make_response

from app.utils.decorators import admin_required
from app.extensions import article_generator, scheduler
from app import config
from database.db_simple import get_connection, DB_CONFIG
from database.user_model_simple import (
    is_admin, delete_user_by_id, get_users_with_stats,
    toggle_user_active, update_user_role, set_magazine_limit,
    get_user_activity, get_user_by_id, add_tokens,
)
from database.article_model_simple import (
    get_article_by_id, publish_article, delete_article,
    get_all_articles_admin, count_all_articles_admin,
    hide_article, unhide_article, flag_article, unflag_article, get_content_stats,
)
from database.system_model import (
    get_all_settings, get_generation_logs, count_generation_logs,
    get_log_stats, get_all_schedules_detail,
    admin_toggle_schedule_db, admin_delete_schedule_db,
    init_settings_table, save_settings_bulk,
)
from database.plan_model import (
    get_all_plans, get_plan_by_id, create_plan, update_plan,
    toggle_plan_active, delete_plan,
    get_all_subscriptions, count_all_subscriptions,
    create_subscription, update_subscription_status,
    renew_subscription, get_subscription_by_id,
    add_payment, get_payments, get_revenue_stats,
)
from database.feedback_model import get_feedback_messages, get_feedback_stats
from dotenv import load_dotenv


def register_routes(app):

    # ------------------------------------------------------------------
    # Admin panel
    # ------------------------------------------------------------------

    @app.route("/admin")
    @admin_required
    def admin_panel():
        return redirect('/admin/panel')

    @app.route("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        return redirect('/admin/panel')

    @app.route("/admin/panel")
    @admin_required
    def admin_panel_new():
        provider_key_map = {
            'groq': 'GROQ_API_KEY',
            'gemini': 'GEMINI_API_KEY',
            'gpt': 'OPENAI_API_KEY',
        }
        current_ai_provider = (os.getenv('ACTIVE_AI_PROVIDER', 'groq') or 'groq').strip().lower()
        if current_ai_provider not in provider_key_map:
            current_ai_provider = 'groq'
        current_ai_model = (
            os.getenv('ACTIVE_AI_MODEL')
            or ('llama-3.3-70b-versatile' if current_ai_provider == 'groq'
                else ('gemini-2.5-flash-lite' if current_ai_provider == 'gemini' else 'gpt-4o-mini'))
        ).strip()
        raw_key = os.getenv(provider_key_map[current_ai_provider], '')
        if len(raw_key) > 14:
            masked_key = raw_key[:8] + '*' * (len(raw_key) - 12) + raw_key[-4:]
        else:
            masked_key = '*' * len(raw_key)

        stats = {}; users = []; top_mags = []; recent_arts = []
        articles_per_day = []; plans = []; schedules = []; settings = {}
        all_magazines = []; new_users_week = 0
        kpi_trends = []
        activity_heatmap = {
            'days': ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'],
            'hours': list(range(24)),
            'grid': [[0 for _ in range(24)] for _ in range(7)],
            'max': 0,
        }
        revenue_stats = {}; sepay_summary = {'paid_amount': 0, 'paid_orders': 0, 'pending_orders': 0, 'paid_tokens': 0, 'today_amount': 0, 'month_amount': 0}

        conn = get_connection()
        if conn:
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute("""
                    SELECT
                        (SELECT COUNT(*) FROM users)                             AS total_users,
                        (SELECT COUNT(*) FROM users WHERE role='admin')          AS total_admins,
                        (SELECT COUNT(*) FROM magazines)                         AS total_magazines,
                        (SELECT COUNT(*) FROM articles)                          AS total_articles,
                        (SELECT COUNT(*) FROM articles WHERE status='published') AS published_articles,
                        (SELECT COALESCE(SUM(view_count),0) FROM articles)       AS total_views,
                        (SELECT COUNT(*) FROM magazine_schedules WHERE is_active=1) AS active_schedules,
                        (SELECT COUNT(*) FROM magazine_schedules)                AS total_schedules,
                        (SELECT COUNT(*) FROM users
                         WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY))   AS new_users_week
                """)
                row = cur.fetchone()
                if row:
                    new_users_week = row.pop('new_users_week', 0) or 0
                    stats = row
                # (top_mags, recent_arts, articles_per_day, kpi_trends, heatmap deferred to /admin/api/overview-data)
                cur.execute("SELECT * FROM subscription_plans ORDER BY price_monthly ASC")
                plans = cur.fetchall()
                cur.execute("""
                    SELECT s.id, s.frequency, s.interval_minutes, s.num_articles,
                           s.is_active, s.last_run, s.created_at,
                           m.title AS magazine_title, u.email AS owner_email
                    FROM magazine_schedules s
                    LEFT JOIN magazines m ON m.id = s.magazine_id
                    LEFT JOIN users u ON u.id = s.user_id
                    ORDER BY s.is_active DESC, s.last_run DESC
                """)
                schedules = cur.fetchall()
                cur.execute(
                    "SELECT `key`, `value`, `label`, `type` FROM system_settings ORDER BY `key`"
                )
                settings = {r['key']: r for r in cur.fetchall()}
                # SePay summary - tất cả trong 1 query
                cur.execute("""
                    SELECT
                        IFNULL(SUM(CASE WHEN status='paid' THEN amount ELSE 0 END),0)                       AS paid_amount,
                        SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END)                                      AS paid_orders,
                        SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END)                                   AS pending_orders,
                        IFNULL(SUM(CASE WHEN status='paid' THEN tokens ELSE 0 END),0)                       AS paid_tokens,
                        IFNULL(SUM(CASE WHEN status='paid' AND DATE(created_at)=CURDATE() THEN amount ELSE 0 END),0) AS today_amount,
                        IFNULL(SUM(CASE WHEN status='paid' AND YEAR(created_at)=YEAR(NOW()) AND MONTH(created_at)=MONTH(NOW()) THEN amount ELSE 0 END),0) AS month_amount
                    FROM sepay_orders
                """)
                ps = cur.fetchone() or {}
                sepay_summary = {
                    'paid_amount':    int(ps.get('paid_amount') or 0),
                    'paid_orders':    int(ps.get('paid_orders') or 0),
                    'pending_orders': int(ps.get('pending_orders') or 0),
                    'paid_tokens':    int(ps.get('paid_tokens') or 0),
                    'today_amount':   int(ps.get('today_amount') or 0),
                    'month_amount':   int(ps.get('month_amount') or 0),
                }
                cur.close()
            except Exception as e:
                print(f"admin_panel_new error: {e}")
            finally:
                conn.close()

        try:
            revenue_stats = {}  # Deferred - not used in template
        except Exception:
            pass

        from datetime import date as _date
        payment_gateway = (settings.get('payment_gateway', {}).get('value') if settings else None) or 'sepay'
        payment_sepay_enabled = ((settings.get('payment_sepay_enabled', {}).get('value') if settings else '1') or '1') == '1'
        payment_vnpay_enabled = ((settings.get('payment_vnpay_enabled', {}).get('value') if settings else '0') or '0') == '1'
        resp = make_response(render_template(
            'admin_panel_new.html',
            stats=stats, users=users, all_magazines=all_magazines,
            top_mags=[], recent_arts=[],
            articles_per_day=[], plans=plans,
            schedules=schedules, settings=settings,
            kpi_trends=[], activity_heatmap={},
            masked_key=masked_key, new_users_week=new_users_week,
            revenue_stats=revenue_stats, sepay_summary=sepay_summary,
            current_ai_provider=current_ai_provider,
            current_ai_model=current_ai_model,
            payment_gateway=payment_gateway,
            payment_sepay_enabled=payment_sepay_enabled,
            payment_vnpay_enabled=payment_vnpay_enabled,
            vnpay_tmn_code=config.VNPAY_TMN_CODE,
            vnpay_payment_url=config.VNPAY_PAYMENT_URL,
            vnpay_return_url=config.VNPAY_RETURN_URL,
            now_date=str(_date.today()),
        ))
        resp.headers['Cache-Control'] = 'private, max-age=30, stale-while-revalidate=60'
        return resp

    # ------------------------------------------------------------------
    # Admin API (lazy-loaded tabs)
    # ------------------------------------------------------------------

    @app.route("/admin/api/quick-stats")
    @admin_required
    def admin_api_quick_stats():
        """Fast KPI counts for the reload button — single-query, no-cache."""
        conn = get_connection()
        if not conn:
            return jsonify({})
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM users)                                             AS total_users,
                    (SELECT COUNT(*) FROM users WHERE role='admin')                          AS total_admins,
                    (SELECT COUNT(*) FROM magazines)                                         AS total_magazines,
                    (SELECT COUNT(*) FROM articles)                                          AS total_articles,
                    (SELECT COUNT(*) FROM articles WHERE status='published')                 AS published_articles,
                    (SELECT COALESCE(SUM(view_count),0) FROM articles)                      AS total_views,
                    (SELECT COUNT(*) FROM magazine_schedules WHERE is_active=1)             AS active_schedules,
                    (SELECT COUNT(*) FROM magazine_schedules)                               AS total_schedules,
                    (SELECT COUNT(*) FROM users WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)) AS new_users_week
            """)
            row = cur.fetchone() or {}
            cur.close(); conn.close()
            result = {k: int(v or 0) for k, v in row.items()}
            resp = jsonify(result)
            resp.headers['Cache-Control'] = 'no-store'
            return resp
        except Exception as e:
            print(f"[ERR] admin_api_quick_stats: {e}")
            return jsonify({})

    @app.route("/admin/api/revenue-kpi")
    @admin_required
    def admin_api_revenue_kpi():
        """Return today + month revenue KPI from sepay_orders."""
        conn = get_connection()
        if not conn:
            return jsonify({'today': 0, 'month': 0, 'total': 0, 'tokens': 0, 'pending': 0})
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT
                    IFNULL(SUM(CASE WHEN status='paid' AND DATE(created_at)=CURDATE() THEN amount ELSE 0 END),0) AS today,
                    IFNULL(SUM(CASE WHEN status='paid' AND YEAR(created_at)=YEAR(NOW()) AND MONTH(created_at)=MONTH(NOW()) THEN amount ELSE 0 END),0) AS month,
                    IFNULL(SUM(CASE WHEN status='paid' THEN amount ELSE 0 END),0) AS total,
                    IFNULL(SUM(CASE WHEN status='paid' THEN tokens ELSE 0 END),0) AS tokens,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending
                FROM sepay_orders
            """)
            row = cur.fetchone() or {}
            cur.close(); conn.close()
            resp = jsonify({
                'today':   int(row.get('today') or 0),
                'month':   int(row.get('month') or 0),
                'total':   int(row.get('total') or 0),
                'tokens':  int(row.get('tokens') or 0),
                'pending': int(row.get('pending') or 0),
            })
            resp.headers['Cache-Control'] = 'private, max-age=60'
            return resp
        except Exception as e:
            print(f"[ERR] admin_api_revenue_kpi: {e}")
            return jsonify({'today': 0, 'month': 0, 'total': 0, 'tokens': 0, 'pending': 0})

    @app.route("/admin/api/overview-data")
    @admin_required
    def admin_api_overview_data():
        """Deferred heavy overview data: kpi_trends, heatmap, top_mags, recent_arts, articles_per_day."""
        kpi_trends = []
        activity_heatmap = {
            'days': ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'],
            'hours': list(range(24)),
            'grid': [[0] * 24 for _ in range(7)],
            'max': 0,
        }
        top_mags = []
        recent_arts = []
        articles_per_day = []
        conn = get_connection()
        if not conn:
            return jsonify({'kpi_trends': kpi_trends, 'activity_heatmap': activity_heatmap,
                            'top_mags': top_mags, 'recent_arts': recent_arts,
                            'articles_per_day': articles_per_day})
        try:
            cur = conn.cursor(dictionary=True)
            # top_mags
            cur.execute("""
                SELECT m.id, m.title, COUNT(a.id) AS article_count,
                       u.email AS owner_email, u.full_name AS owner_name
                FROM magazines m
                LEFT JOIN articles a ON a.magazine_id = m.id
                LEFT JOIN users u ON u.id = m.user_id
                GROUP BY m.id, m.title, u.email, u.full_name
                ORDER BY article_count DESC LIMIT 10
            """)
            for r in cur.fetchall():
                top_mags.append({'id': r['id'], 'title': r['title'],
                                 'article_count': int(r['article_count'] or 0),
                                 'owner_name': r.get('owner_name') or '',
                                 'owner_email': r.get('owner_email') or ''})
            # recent_arts
            cur.execute("""
                SELECT a.id, a.title, a.status,
                       DATE_FORMAT(a.created_at, '%Y-%m-%d') AS created_at,
                       m.title AS magazine_title,
                       u.email AS author_email, u.full_name AS author_name
                FROM articles a
                LEFT JOIN magazines m ON m.id = a.magazine_id
                LEFT JOIN users u ON u.id = a.user_id
                ORDER BY a.created_at DESC LIMIT 15
            """)
            for r in cur.fetchall():
                recent_arts.append({'id': r['id'], 'title': r['title'],
                                    'status': r.get('status') or '',
                                    'created_at': str(r.get('created_at') or ''),
                                    'magazine_title': r.get('magazine_title') or '',
                                    'author_name': r.get('author_name') or '',
                                    'author_email': r.get('author_email') or ''})
            # articles_per_day
            cur.execute("""
                SELECT DATE(created_at) AS day, COUNT(*) AS count
                FROM articles
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
                GROUP BY DATE(created_at) ORDER BY day ASC
            """)
            articles_per_day = [{'day': str(r['day']), 'count': int(r['count'])} for r in cur.fetchall()]
            # kpi_trends (4 queries combined via UNION)
            from datetime import timedelta
            _today = datetime.now().date()
            trend_days = [_today - timedelta(days=i) for i in range(13, -1, -1)]
            def _build_series(query):
                cur.execute(query)
                _map = {str(d): 0 for d in trend_days}
                for _r in (cur.fetchall() or []):
                    _key = str(_r.get('day'))
                    if _key in _map:
                        _map[_key] = int(_r.get('count') or 0)
                return [_map[str(d)] for d in trend_days]
            def _trend_payload(key, label, color, series):
                c7, p7 = sum(series[-7:]), sum(series[-14:-7])
                diff = c7 - p7
                pct = round((diff / p7) * 100, 1) if p7 > 0 else (100.0 if c7 > 0 else 0.0)
                return {'key': key, 'label': label, 'color': color, 'series': series,
                        'current7': int(c7), 'prev7': int(p7), 'pct': pct,
                        'direction': 'up' if diff > 0 else ('down' if diff < 0 else 'flat')}
            kpi_trends = [
                _trend_payload('users', 'Người dùng mới', '#4f46e5', _build_series(
                    "SELECT DATE(created_at) AS day, COUNT(*) AS count FROM users WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 14 DAY) GROUP BY DATE(created_at)")),
                _trend_payload('magazines', 'Tạp chí mới', '#7c3aed', _build_series(
                    "SELECT DATE(created_at) AS day, COUNT(*) AS count FROM magazines WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 14 DAY) GROUP BY DATE(created_at)")),
                _trend_payload('articles', 'Bài viết tạo mới', '#059669', _build_series(
                    "SELECT DATE(created_at) AS day, COUNT(*) AS count FROM articles WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 14 DAY) GROUP BY DATE(created_at)")),
                _trend_payload('published', 'Bài đã xuất bản', '#d97706', _build_series(
                    "SELECT DATE(COALESCE(published_at, created_at)) AS day, COUNT(*) AS count FROM articles WHERE status='published' AND COALESCE(published_at, created_at) >= DATE_SUB(CURDATE(), INTERVAL 14 DAY) GROUP BY DATE(COALESCE(published_at, created_at))")),
            ]
            # heatmap
            cur.execute("""
                SELECT WEEKDAY(created_at) AS wd, HOUR(created_at) AS hr, COUNT(*) AS count
                FROM articles WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY WEEKDAY(created_at), HOUR(created_at)
            """)
            heat_grid = [[0] * 24 for _ in range(7)]
            max_heat = 0
            for hr in (cur.fetchall() or []):
                wd, hh, cnt = int(hr.get('wd') or 0), int(hr.get('hr') or 0), int(hr.get('count') or 0)
                if 0 <= wd <= 6 and 0 <= hh <= 23:
                    heat_grid[wd][hh] = cnt
                    if cnt > max_heat:
                        max_heat = cnt
            activity_heatmap = {'days': ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'],
                                 'hours': list(range(24)), 'grid': heat_grid, 'max': int(max_heat)}
            cur.close()
        except Exception as e:
            print(f"[ERR] admin_api_overview_data: {e}")
        finally:
            conn.close()
        return jsonify({'kpi_trends': kpi_trends, 'activity_heatmap': activity_heatmap,
                        'top_mags': top_mags, 'recent_arts': recent_arts,
                        'articles_per_day': articles_per_day})

    @app.route('/admin/api/feedback')
    @admin_required
    def admin_api_feedback():
        try:
            rows = get_feedback_messages(limit=300)
            stats = get_feedback_stats()
            for r in rows:
                if r.get('created_at'):
                    r['created_at'] = str(r['created_at'])[:19]
            return jsonify({'stats': stats, 'items': rows})
        except Exception as e:
            print(f"[ERR] admin_api_feedback: {e}")
            return jsonify({'stats': {'total': 0, 'new': 0, 'today': 0}, 'items': []})


    @app.route("/admin/api/users")
    @admin_required
    def admin_api_users():
        conn = get_connection()
        if not conn:
            return jsonify([])
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.created_at,
                       COALESCE(u.token_balance, 0) AS token_balance,
                       COALESCE(u.auth_provider, 'local') AS auth_provider,
                       (SELECT COUNT(*) FROM magazines WHERE user_id = u.id) AS magazine_count,
                       (SELECT COUNT(*) FROM articles  WHERE user_id = u.id) AS article_count
                FROM users u
                ORDER BY u.created_at DESC
            """)
            rows = cur.fetchall() or []
            cur.close(); conn.close()
            for r in rows:
                if r.get('created_at'):
                    r['created_at'] = str(r['created_at'])[:10]
                r['token_balance'] = int(r.get('token_balance') or 0)
                r['is_active'] = bool(r.get('is_active'))
            resp = jsonify(rows)
            resp.headers['Cache-Control'] = 'private, max-age=30'
            return resp
        except Exception as e:
            print(f"[ERR] admin_api_users: {e}")
            return jsonify([])

    @app.route("/admin/api/magazines")
    @admin_required
    def admin_api_magazines():
        conn = get_connection()
        if not conn:
            return jsonify([])
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT m.id, m.title, m.topic, m.slug, m.created_at,
                       u.email AS owner_email, u.full_name AS owner_name,
                       (SELECT COUNT(*) FROM articles  WHERE magazine_id = m.id)                AS article_count,
                       (SELECT COUNT(*) > 0 FROM magazine_schedules
                        WHERE magazine_id = m.id AND is_active = 1)                            AS has_schedule
                FROM magazines m
                LEFT JOIN users u ON u.id = m.user_id
                ORDER BY m.created_at DESC
            """)
            rows = cur.fetchall() or []
            cur.close(); conn.close()
            for r in rows:
                if r.get('created_at'):
                    r['created_at'] = str(r['created_at'])[:10]
                r['has_schedule'] = bool(r.get('has_schedule'))
            resp = jsonify(rows)
            resp.headers['Cache-Control'] = 'private, max-age=30'
            return resp
        except Exception as e:
            print(f"[ERR] admin_api_magazines: {e}")
            return jsonify([])

    @app.route("/admin/api/magazine/<int:mag_id>", methods=["DELETE"])
    @admin_required
    def admin_api_delete_magazine(mag_id):
        """Admin hard-delete a magazine with all its articles and schedules."""
        conn = get_connection()
        if not conn:
            return jsonify({'ok': False, 'error': 'DB error'}), 500
        try:
            cur = conn.cursor()
            # Delete articles (no FK cascade on magazine_id column)
            cur.execute("DELETE FROM articles WHERE magazine_id = %s", (mag_id,))
            # Delete magazine — magazine_schedules cascade automatically
            cur.execute("DELETE FROM magazines WHERE id = %s", (mag_id,))
            conn.commit()
            affected = cur.rowcount
            cur.close(); conn.close()
            if affected:
                return jsonify({'ok': True})
            return jsonify({'ok': False, 'error': 'Kh\u00f4ng t\u00ecm th\u1ea5y t\u1ea1p ch\u00ed'}), 404
        except Exception as e:
            print(f"[ERR] admin_api_delete_magazine: {e}")
            if conn:
                conn.close()
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route("/admin/api/sepay-orders")
    @admin_required
    def admin_api_sepay_orders():
        conn = get_connection()
        if not conn:
            return jsonify([])
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT p.order_code, p.plan_name, p.amount, p.tokens,
                       p.status, p.created_at,
                       u.email
                FROM sepay_orders p
                LEFT JOIN users u ON u.id = p.user_id
                ORDER BY p.created_at DESC
                LIMIT 100
            """)
            rows = cur.fetchall() or []
            cur.close(); conn.close()
            for r in rows:
                if r.get('created_at'):
                    r['created_at'] = str(r['created_at'])[:16]
                r['amount'] = int(r.get('amount') or 0)
                r['tokens'] = int(r.get('tokens') or 0)
            return jsonify(rows)
        except Exception as e:
            print(f"[ERR] admin_api_sepay_orders: {e}")
            return jsonify([])

    @app.route("/admin/api/payos-orders")
    @admin_required
    def admin_api_payos_orders_compat():
        return admin_api_sepay_orders()

    @app.route("/admin/api/revenue-filter")
    @admin_required
    def admin_api_revenue_filter():
        """Return daily SePay revenue + tokens for a given date range."""
        from datetime import datetime, timedelta
        mode     = request.args.get('mode', 'month')   # day | week | month | custom
        date_from = request.args.get('from', '')
        date_to   = request.args.get('to', '')
        today    = datetime.today().date()

        if mode == 'week':
            d_from = today - timedelta(days=today.weekday())
            d_to   = today
        elif mode == 'month':
            d_from = today.replace(day=1)
            d_to   = today
        elif mode == 'custom' and date_from and date_to:
            try:
                d_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                d_to   = datetime.strptime(date_to,   '%Y-%m-%d').date()
                if d_to > today: d_to = today
            except ValueError:
                d_from = today.replace(day=1); d_to = today
        else:
            d_from = today.replace(day=1); d_to = today

        conn = get_connection()
        if not conn:
            return jsonify({'rows': [], 'total_amount': 0, 'total_tokens': 0})
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT DATE(created_at) AS day,
                       SUM(amount) AS total_amount,
                       SUM(tokens) AS total_tokens,
                       COUNT(*) AS orders
                FROM sepay_orders
                WHERE status='paid'
                  AND DATE(created_at) BETWEEN %s AND %s
                GROUP BY DATE(created_at)
                ORDER BY day
            """, (str(d_from), str(d_to)))
            rows = cur.fetchall() or []
            cur.close(); conn.close()
            for r in rows:
                r['day'] = str(r['day'])
                r['total_amount'] = int(r['total_amount'] or 0)
                r['total_tokens'] = int(r['total_tokens'] or 0)
                r['orders'] = int(r['orders'] or 0)
            # Compute totals from daily rows — saves a second DB round-trip
            total_amount = sum(r['total_amount'] for r in rows)
            total_tokens = sum(r['total_tokens'] for r in rows)
            total_orders = sum(r['orders'] for r in rows)
            resp = jsonify({
                'rows': rows,
                'total_amount': total_amount,
                'total_tokens': total_tokens,
                'total_orders': total_orders,
                'date_from': str(d_from),
                'date_to':   str(d_to),
            })
            resp.headers['Cache-Control'] = 'private, max-age=30'
            return resp
        except Exception as e:
            print(f"[ERR] admin_api_revenue_filter: {e}")
            return jsonify({'rows': [], 'total_amount': 0, 'total_tokens': 0, 'total_orders': 0})

    # ------------------------------------------------------------------
    # Article moderation
    # ------------------------------------------------------------------

    @app.route("/admin/approve/<int:article_id>", methods=["POST"])
    @admin_required
    def approve_article(article_id):
        conn = get_connection()
        if not conn:
            flash('Lỗi kết nối database', 'error')
            return redirect('/admin')
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE articles SET status='published', published_at=NOW() "
                "WHERE id=%s AND status='pending'",
                (article_id,),
            )
            affected = cursor.rowcount
            conn.commit(); cursor.close(); conn.close()
            if affected > 0:
                flash('Bài viết đã được phê duyệt và xuất bản', 'success')
            else:
                flash('Không tìm thấy bài viết chờ duyệt', 'warning')
        except Exception as e:
            print(f"❌ Error approving article: {e}")
            flash('Lỗi khi duyệt bài viết', 'error')
        return redirect('/admin?status=pending')

    @app.route("/admin/reject/<int:article_id>", methods=["POST"])
    @admin_required
    def reject_article(article_id):
        conn = get_connection()
        if not conn:
            flash('Lỗi kết nối database', 'error')
            return redirect('/admin')
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE articles SET status='draft' WHERE id=%s AND status='pending'",
                (article_id,),
            )
            affected = cursor.rowcount
            conn.commit(); cursor.close(); conn.close()
            if affected > 0:
                flash('Bài viết đã bị từ chối và chuyển về nháp', 'info')
            else:
                flash('Không tìm thấy bài viết chờ duyệt', 'warning')
        except Exception as e:
            print(f"❌ Error rejecting article: {e}")
            flash('Lỗi khi từ chối bài viết', 'error')
        return redirect('/admin?status=pending')

    @app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
    @admin_required
    def delete_user(user_id):
        from flask import jsonify, request as flask_request
        is_ajax = flask_request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if user_id == session['user_id']:
            if is_ajax:
                return jsonify(success=False, message='Không thể tự xóa chính mình!')
            flash('Không thể tự xóa chính mình!', 'error')
            return redirect('/dashboard?tab=admin')
        success = delete_user_by_id(user_id)
        if is_ajax:
            return jsonify(success=success)
        if success:
            flash('Đã xóa người dùng thành công!', 'success')
        else:
            flash('Xóa người dùng thất bại!', 'error')
        return redirect('/dashboard?tab=admin')

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    @app.route("/admin/users/<int:uid>/grant-tokens", methods=["POST"])
    @admin_required
    def admin_grant_tokens(uid):
        data = request.get_json(silent=True) or {}
        try:
            amount = int(data.get('amount', 0))
        except (ValueError, TypeError):
            return jsonify(success=False, message='Số token không hợp lệ')
        if amount == 0:
            return jsonify(success=False, message='Số token phải khác 0')
        new_balance = add_tokens(uid, amount)
        if new_balance is None:
            return jsonify(success=False, message='Cập nhật token thất bại')
        return jsonify(success=True, new_balance=new_balance)

    @app.route("/admin/users")
    @admin_required
    def admin_users():
        users = get_users_with_stats()
        return render_template("admin_users.html", users=users)

    @app.route("/admin/users/<int:uid>")
    @admin_required
    def admin_user_detail(uid):
        user = get_user_by_id(uid)
        if not user:
            flash('Người dùng không tồn tại!', 'error')
            return redirect('/admin/users')
        activity = get_user_activity(uid, limit=30)
        return render_template(
            "admin_users.html",
            users=get_users_with_stats(),
            selected_user=user, activity=activity,
        )

    @app.route("/admin/users/<int:uid>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_user(uid):
        if uid == session['user_id']:
            return jsonify({'error': 'Không thể khóa chính mình'}), 400
        new_state = toggle_user_active(uid)
        if new_state is None:
            return jsonify({'error': 'Không tìm thấy user'}), 404
        return jsonify({'is_active': new_state})

    @app.route("/admin/users/<int:uid>/role", methods=["POST"])
    @admin_required
    def admin_set_role(uid):
        if uid == session['user_id']:
            flash('Không thể đổi role của chính mình', 'error')
            return redirect('/dashboard?tab=admin')
        role = request.form.get('role', '')
        if role not in ['user', 'premium', 'admin']:
            flash('Role không hợp lệ', 'error')
            return redirect('/dashboard?tab=admin')
        update_user_role(uid, role)
        return redirect('/dashboard?tab=admin')

    @app.route("/admin/users/<int:uid>/limit", methods=["POST"])
    @admin_required
    def admin_set_limit(uid):
        limit = request.form.get('limit', 10)
        try:
            limit = int(limit)
            if limit < 1:
                limit = 1
        except Exception:
            return jsonify({'error': 'Limit không hợp lệ'}), 400
        ok = set_magazine_limit(uid, limit)
        return jsonify({'success': ok, 'limit': limit})

    # ------------------------------------------------------------------
    # Content management
    # ------------------------------------------------------------------

    @app.route("/admin/content")
    @admin_required
    def admin_content():
        status   = request.args.get('status', '')
        keyword  = request.args.get('q', '').strip()
        flagged  = request.args.get('flagged', '') == '1'
        page     = max(int(request.args.get('page', 1)), 1)
        per_page = 25
        offset   = (page - 1) * per_page
        articles = get_all_articles_admin(
            status=status or None, flagged_only=flagged,
            keyword=keyword or None, limit=per_page, offset=offset,
        )
        total = count_all_articles_admin(status=status or None, flagged_only=flagged, keyword=keyword or None)
        stats = get_content_stats()
        pages = max(1, (total + per_page - 1) // per_page)
        return render_template(
            'admin_content.html',
            articles=articles, stats=stats,
            current_status=status, current_q=keyword, current_flagged=flagged,
            page=page, pages=pages, total=total,
        )

    @app.route("/admin/content/<int:aid>/hide", methods=["POST"])
    @admin_required
    def admin_hide_article(aid):
        ok = hide_article(aid)
        return jsonify({'success': ok, 'status': 'hidden'})

    @app.route("/admin/content/<int:aid>/unhide", methods=["POST"])
    @admin_required
    def admin_unhide_article(aid):
        ok = unhide_article(aid)
        return jsonify({'success': ok, 'status': 'published'})

    @app.route("/admin/content/<int:aid>/flag", methods=["POST"])
    @admin_required
    def admin_flag_article(aid):
        reason = request.form.get('reason', '')
        ok     = flag_article(aid, reason)
        return jsonify({'success': ok})

    @app.route("/admin/content/<int:aid>/unflag", methods=["POST"])
    @admin_required
    def admin_unflag_article(aid):
        ok = unflag_article(aid)
        return jsonify({'success': ok})

    @app.route("/admin/content/<int:aid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_article(aid):
        ok = delete_article(aid)
        return jsonify({'success': ok})

    @app.route("/admin/content/<int:aid>/approve", methods=["POST"])
    @admin_required
    def admin_approve_article(aid):
        ok = publish_article(aid, session['user_id'])
        return jsonify({'success': bool(ok)})

    # ------------------------------------------------------------------
    # System management
    # ------------------------------------------------------------------

    @app.route("/admin/system")
    @admin_required
    def admin_system():
        log_tab  = request.args.get('logs', 'all')
        log_page = max(int(request.args.get('lp', 1)), 1)
        per_page = 30
        log_status = None if log_tab == 'all' else log_tab
        logs       = get_generation_logs(status=log_status, limit=per_page, offset=(log_page - 1) * per_page)
        log_count  = count_generation_logs(status=log_status)
        log_pages  = max(1, (log_count + per_page - 1) // per_page)
        log_stats  = get_log_stats()
        schedules  = get_all_schedules_detail()
        settings   = {s['key']: s for s in get_all_settings()}
        raw_key    = os.getenv('GROQ_API_KEY', '')
        masked_key = (
            raw_key[:8] + '*' * (len(raw_key) - 12) + raw_key[-4:]
            if len(raw_key) > 14 else '*' * len(raw_key)
        )
        running_jobs = [j.id for j in scheduler.get_jobs()]
        return render_template(
            'admin_system.html',
            logs=logs, log_stats=log_stats, log_tab=log_tab,
            log_page=log_page, log_pages=log_pages, log_count=log_count,
            schedules=schedules, settings=settings,
            masked_key=masked_key, running_jobs=running_jobs,
        )

    @app.route("/admin/system/settings", methods=["POST"])
    @admin_required
    def admin_save_settings():
        keys = ['daily_article_limit', 'max_articles_per_gen',
                'maintenance_mode', 'site_name', 'contact_email']
        data = {k: request.form.get(k, '') for k in keys}
        ok   = save_settings_bulk(data)
        return jsonify({'success': ok})

    @app.route("/admin/system/apikey", methods=["POST"])
    @admin_required
    def admin_save_apikey():
        provider_key_map = {
            'groq': 'GROQ_API_KEY',
            'gemini': 'GEMINI_API_KEY',
            'gpt': 'OPENAI_API_KEY',
        }
        provider = (request.form.get('provider', 'groq') or 'groq').strip().lower()
        if provider not in provider_key_map:
            return jsonify({'error': 'Provider không hợp lệ'}), 400
        model = (request.form.get('model', '') or '').strip()
        if not model:
            model = (
                'llama-3.3-70b-versatile' if provider == 'groq'
                else ('gemini-2.5-flash-lite' if provider == 'gemini' else 'gpt-4o-mini')
            )
        new_key = request.form.get('api_key', '').strip()
        env_path = os.path.join(config.BASE_DIR, '.env')
        try:
            if os.path.exists(env_path):
                content = open(env_path, 'r', encoding='utf-8').read()
                if re.search(r'^ACTIVE_AI_PROVIDER\s*=', content, re.MULTILINE):
                    content = re.sub(r'^(ACTIVE_AI_PROVIDER\s*=).*', f'\\g<1>{provider}', content, flags=re.MULTILINE)
                else:
                    content += f'\nACTIVE_AI_PROVIDER={provider}\n'
                if re.search(r'^ACTIVE_AI_MODEL\s*=', content, re.MULTILINE):
                    content = re.sub(r'^(ACTIVE_AI_MODEL\s*=).*', f'\\g<1>{model}', content, flags=re.MULTILINE)
                else:
                    content += f'ACTIVE_AI_MODEL={model}\n'
                if new_key:
                    key_name = provider_key_map[provider]
                    if re.search(rf'^{key_name}\s*=', content, re.MULTILINE):
                        content = re.sub(
                            rf'^({key_name}\s*=).*', f'\\g<1>{new_key}',
                            content, flags=re.MULTILINE,
                        )
                    else:
                        content += f'{key_name}={new_key}\n'
            else:
                lines = [
                    f'ACTIVE_AI_PROVIDER={provider}',
                    f'ACTIVE_AI_MODEL={model}',
                ]
                if new_key:
                    lines.append(f'{provider_key_map[provider]}={new_key}')
                content = '\n'.join(lines) + '\n'
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(content)
            load_dotenv(dotenv_path=env_path, override=True)
            os.environ['ACTIVE_AI_PROVIDER'] = provider
            os.environ['ACTIVE_AI_MODEL'] = model
            if new_key:
                os.environ[provider_key_map[provider]] = new_key
            # Giữ nguyên tương thích runtime hiện tại (Groq) để không ảnh hưởng luồng sinh bài đang chạy.
            if provider == 'groq' and new_key:
                article_generator.api_key = new_key
                if hasattr(article_generator, 'client') and article_generator.client:
                    try:
                        from groq import Groq
                        article_generator.client = Groq(api_key=new_key)
                    except Exception:
                        pass
                if hasattr(article_generator, 'model_name'):
                    article_generator.model_name = model
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route("/admin/payment/settings", methods=["POST"])
    @admin_required
    def admin_save_payment_settings():
        gateway = (request.form.get("payment_gateway") or "sepay").strip().lower()
        sepay_enabled = 1 if request.form.get("payment_sepay_enabled") else 0
        vnpay_enabled = 1 if request.form.get("payment_vnpay_enabled") else 0
        if gateway not in ("sepay", "vnpay"):
            return jsonify({"success": False, "error": "Gateway không hợp lệ"}), 400
        if not sepay_enabled and not vnpay_enabled:
            return jsonify({"success": False, "error": "Cần bật ít nhất một cổng thanh toán"}), 400
        if gateway == "sepay" and not sepay_enabled:
            return jsonify({"success": False, "error": "SePay đang tắt, không thể đặt làm mặc định"}), 400
        if gateway == "vnpay" and not vnpay_enabled:
            return jsonify({"success": False, "error": "VNPAY đang tắt, không thể đặt làm mặc định"}), 400

        vnpay_tmn_code = (request.form.get("vnpay_tmn_code") or "").strip()
        vnpay_hash_secret = (request.form.get("vnpay_hash_secret") or "").strip()
        vnpay_payment_url = (request.form.get("vnpay_payment_url") or "").strip()
        vnpay_return_url = (request.form.get("vnpay_return_url") or "").strip()

        if vnpay_enabled and gateway == "vnpay":
            if not (vnpay_tmn_code or config.VNPAY_TMN_CODE):
                return jsonify({"success": False, "error": "Thiếu VNPAY_TMN_CODE"}), 400
            if not (vnpay_hash_secret or config.VNPAY_HASH_SECRET):
                return jsonify({"success": False, "error": "Thiếu VNPAY_HASH_SECRET"}), 400

        settings_ok = save_settings_bulk({
            "payment_gateway": gateway,
            "payment_sepay_enabled": str(sepay_enabled),
            "payment_vnpay_enabled": str(vnpay_enabled),
        })
        if not settings_ok:
            return jsonify({"success": False, "error": "Không thể lưu setting thanh toán"}), 500

        env_updates = {}
        if vnpay_tmn_code:
            env_updates["VNPAY_TMN_CODE"] = vnpay_tmn_code
        if vnpay_hash_secret:
            env_updates["VNPAY_HASH_SECRET"] = vnpay_hash_secret
        if vnpay_payment_url:
            env_updates["VNPAY_PAYMENT_URL"] = vnpay_payment_url
        if vnpay_return_url:
            env_updates["VNPAY_RETURN_URL"] = vnpay_return_url

        if env_updates:
            env_path = os.path.join(config.BASE_DIR, ".env")
            try:
                content = open(env_path, "r", encoding="utf-8").read() if os.path.exists(env_path) else ""
                for key, value in env_updates.items():
                    if re.search(rf"^{key}\s*=", content, re.MULTILINE):
                        content = re.sub(rf"^({key}\s*=).*", rf"\g<1>{value}", content, flags=re.MULTILINE)
                    else:
                        if content and not content.endswith("\n"):
                            content += "\n"
                        content += f"{key}={value}\n"
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)
                load_dotenv(dotenv_path=env_path, override=True)
                for key, value in env_updates.items():
                    os.environ[key] = value
                # Cập nhật config module runtime ngay — không cần restart server
                if "VNPAY_TMN_CODE" in env_updates:
                    config.VNPAY_TMN_CODE = env_updates["VNPAY_TMN_CODE"]
                if "VNPAY_HASH_SECRET" in env_updates:
                    config.VNPAY_HASH_SECRET = env_updates["VNPAY_HASH_SECRET"]
                if "VNPAY_PAYMENT_URL" in env_updates:
                    config.VNPAY_PAYMENT_URL = env_updates["VNPAY_PAYMENT_URL"]
                if "VNPAY_RETURN_URL" in env_updates:
                    config.VNPAY_RETURN_URL = env_updates["VNPAY_RETURN_URL"]
            except Exception as exc:
                return jsonify({"success": False, "error": f"Lưu .env thất bại: {exc}"}), 500

        return jsonify({"success": True})

    @app.route("/admin/system/schedule/<int:sid>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_schedule(sid):
        from app.services.scheduler_service import _register_schedule_job
        from database.schedule_model_simple import get_schedule_by_id as _get_sched
        new_state = admin_toggle_schedule_db(sid)
        if new_state is None:
            return jsonify({'error': 'Không tìm thấy lịch'}), 404
        job_id = f'sched_{sid}'
        if new_state == 1:
            schedule = _get_sched(sid)
            if schedule:
                _register_schedule_job(schedule)
        else:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
        return jsonify({'success': True, 'is_active': new_state})

    @app.route("/admin/system/schedule/<int:sid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_schedule(sid):
        job_id = f'sched_{sid}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        ok = admin_delete_schedule_db(sid)
        return jsonify({'success': ok})

    # ------------------------------------------------------------------
    # Plans & monetization
    # ------------------------------------------------------------------

    @app.route("/admin/plans")
    @admin_required
    def admin_plans():
        tab        = request.args.get('tab', 'plans')
        plans      = get_all_plans()
        sub_status = request.args.get('sub_status', '')
        sub_page   = max(int(request.args.get('sp', 1)), 1)
        sub_per    = 20
        subs       = get_all_subscriptions(status=sub_status or None, limit=sub_per, offset=(sub_page - 1) * sub_per)
        sub_total  = count_all_subscriptions(status=sub_status or None)
        sub_pages  = max(1, (sub_total + sub_per - 1) // sub_per)
        pay_page   = max(int(request.args.get('pp', 1)), 1)
        pay_per    = 20
        payments   = get_payments(limit=pay_per, offset=(pay_page - 1) * pay_per)
        rev_stats  = get_revenue_stats()
        return render_template(
            'admin_plans.html',
            tab=tab, plans=plans,
            subs=subs, sub_status=sub_status, sub_page=sub_page, sub_pages=sub_pages,
            payments=payments, pay_page=pay_page, rev_stats=rev_stats,
            user_email=session['user_email'], user_role=session.get('user_role'),
        )

    @app.route("/admin/plans/create", methods=["POST"])
    @admin_required
    def admin_create_plan():
        name             = request.form.get('name', '').strip()
        price_monthly    = float(request.form.get('price_monthly', 0) or 0)
        magazines_limit  = int(request.form.get('magazines_limit', 2))
        articles_per_day = int(request.form.get('articles_per_day', 3))
        auto_schedule    = 1 if request.form.get('auto_schedule') else 0
        description      = request.form.get('description', '').strip()
        badge_color      = request.form.get('badge_color', '#6c757d').strip()
        sort_order       = int(request.form.get('sort_order', 0) or 0)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if not name:
            if is_ajax: return jsonify(success=False, message='Tên gói không được để trống!')
            flash('Tên gói không được để trống!', 'error')
            return redirect('/admin/plans?tab=plans')
        pid = create_plan(name, price_monthly, magazines_limit, articles_per_day,
                          auto_schedule, description, badge_color, sort_order)
        if is_ajax: return jsonify(success=bool(pid), id=pid)
        if pid:
            flash(f'✅ Đã tạo gói "{name}" thành công!', 'success')
        else:
            flash('❌ Không thể tạo gói, vui lòng thử lại!', 'error')
        return redirect('/admin/plans?tab=plans')

    @app.route("/admin/plans/<int:pid>/edit", methods=["POST"])
    @admin_required
    def admin_edit_plan(pid):
        name             = request.form.get('name', '').strip()
        price_monthly    = float(request.form.get('price_monthly', 0) or 0)
        magazines_limit  = int(request.form.get('magazines_limit', 2))
        articles_per_day = int(request.form.get('articles_per_day', 3))
        auto_schedule    = 1 if request.form.get('auto_schedule') else 0
        description      = request.form.get('description', '').strip()
        badge_color      = request.form.get('badge_color', '#6c757d').strip()
        sort_order       = int(request.form.get('sort_order', 0) or 0)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        ok = update_plan(pid, name, price_monthly, magazines_limit, articles_per_day,
                         auto_schedule, description, badge_color, sort_order)
        if is_ajax: return jsonify(success=bool(ok))
        flash(f'✅ Đã cập nhật gói "{name}"!' if ok else '❌ Cập nhật thất bại!',
              'success' if ok else 'error')
        return redirect('/admin/plans?tab=plans')

    @app.route("/admin/plans/<int:pid>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_plan(pid):
        new_state = toggle_plan_active(pid)
        return jsonify({'success': new_state is not None, 'is_active': new_state})

    @app.route("/admin/plans/<int:pid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_plan(pid):
        ok = delete_plan(pid)
        return jsonify({'success': ok})

    @app.route("/admin/plans/subscribe", methods=["POST"])
    @admin_required
    def admin_create_subscription():
        user_id        = int(request.form.get('user_id', 0))
        plan_id        = int(request.form.get('plan_id', 0))
        months         = int(request.form.get('months', 1) or 1)
        payment_method = request.form.get('payment_method', 'manual').strip()
        amount_paid    = float(request.form.get('amount_paid', 0) or 0)
        notes          = request.form.get('notes', '').strip()
        if not user_id or not plan_id:
            flash('Thiếu thông tin user hoặc gói!', 'error')
            return redirect('/admin/plans?tab=subs')
        sub_id = create_subscription(user_id, plan_id, months, payment_method, amount_paid, notes)
        if sub_id:
            plan = get_plan_by_id(plan_id)
            if plan and amount_paid > 0:
                add_payment(user_id, plan_id, amount_paid, subscription_id=sub_id,
                            payment_method=payment_method, notes=notes)
            flash('✅ Đã kích hoạt gói cho người dùng!', 'success')
        else:
            flash('❌ Không thể tạo đăng ký!', 'error')
        return redirect('/admin/plans?tab=subs')

    @app.route("/admin/plans/sub/<int:sid>/cancel", methods=["POST"])
    @admin_required
    def admin_cancel_subscription(sid):
        ok = update_subscription_status(sid, 'cancelled')
        return jsonify({'success': ok})

    @app.route("/admin/plans/sub/<int:sid>/renew", methods=["POST"])
    @admin_required
    def admin_renew_subscription(sid):
        months = int(request.form.get('months', 1) or 1)
        amount = float(request.form.get('amount', 0) or 0)
        notes  = request.form.get('notes', '').strip()
        ok     = renew_subscription(sid, months, amount, notes)
        if ok and amount > 0:
            sub = get_subscription_by_id(sid)
            if sub:
                add_payment(sub['user_id'], sub['plan_id'], amount,
                            subscription_id=sid, notes=f'Gia hạn {months} tháng')
        flash('✅ Đã gia hạn thành công!' if ok else '❌ Gia hạn thất bại!',
              'success' if ok else 'error')
        return redirect('/admin/plans?tab=subs')

    # ------------------------------------------------------------------
    # Database backup
    # ------------------------------------------------------------------

    @app.route("/admin/system/backup")
    @admin_required
    def admin_backup_db():
        ts    = datetime.now().strftime('%Y%m%d_%H%M%S')
        fname = f"backup_{DB_CONFIG['database']}_{ts}.sql"
        tmp   = tempfile.NamedTemporaryFile(suffix='.sql', delete=False)
        tmp.close()
        mysqldump_paths = [
            r'C:\xampp\mysql\bin\mysqldump.exe',
            r'C:\xampp64\mysql\bin\mysqldump.exe',
            'mysqldump',
        ]
        dump_cmd = None
        for p in mysqldump_paths:
            try:
                subprocess.run([p, '--version'], capture_output=True, timeout=3)
                dump_cmd = p
                break
            except Exception:
                continue
        if not dump_cmd:
            return jsonify({'error': 'Không tìm thấy mysqldump. Hãy kiểm tra XAMPP.'}), 500
        cmd = [
            dump_cmd,
            f"--host={DB_CONFIG['host']}",
            f"--port={DB_CONFIG['port']}",
            f"--user={DB_CONFIG['user']}",
            DB_CONFIG['database'],
            f"--result-file={tmp.name}",
            '--single-transaction', '--routines', '--triggers',
            '--default-character-set=utf8mb4',
        ]
        if DB_CONFIG.get('password'):
            cmd.insert(5, f"--password={DB_CONFIG['password']}")
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode != 0:
                err = result.stderr.decode('utf-8', errors='replace')
                return jsonify({'error': f'mysqldump lỗi: {err}'}), 500
            return send_file(tmp.name, as_attachment=True, download_name=fname,
                             mimetype='application/sql')
        except subprocess.TimeoutExpired:
            return jsonify({'error': 'Timeout khi backup'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500
