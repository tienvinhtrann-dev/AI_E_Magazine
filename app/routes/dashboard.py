"""
Dashboard routes: user dashboard, posts fragment, theme save, settings edit.
"""
import json
import time
from flask import session, flash, redirect, url_for, render_template, request, jsonify

from app.utils.decorators import login_required
from database.db_simple import get_connection
from database.magazine_model_simple import get_magazine_by_id, update_magazine_settings
from database.schedule_model_simple import get_schedules_by_user


def register_routes(app):

    @app.route("/dashboard/posts/fragment")
    @login_required
    def dashboard_posts_fragment():
        user_id       = session['user_id']
        active_mag_id = request.args.get('mag_id', type=int)
        search_query  = request.args.get('q', '').strip() or None
        conn = get_connection()
        articles = []
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                base_sql = """
                    SELECT
                        id, title, summary, keywords, topic,
                        status, view_count, created_at, published_at,
                        image_urls, magazine_id
                    FROM articles
                    WHERE user_id = %s
                """
                params = [user_id]
                if active_mag_id:
                    base_sql += " AND magazine_id = %s"
                    params.append(active_mag_id)
                if search_query:
                    base_sql += " AND (title LIKE %s OR summary LIKE %s OR topic LIKE %s)"
                    like_term = f"%{search_query}%"
                    params.extend([like_term, like_term, like_term])
                base_sql += " ORDER BY created_at DESC"
                cursor.execute(base_sql, params)
                articles = cursor.fetchall() or []
                for a in articles:
                    raw = a.get("image_urls")
                    if raw:
                        try:
                            a["image_urls"] = json.loads(raw)
                        except Exception:
                            a["image_urls"] = []
                    else:
                        a["image_urls"] = []
                cursor.close()
            except Exception as e:
                print(f"[ERR] dashboard_posts_fragment: {e}")
            finally:
                conn.close()
        return render_template("_dashboard_posts.html", articles=articles)

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user_id      = session['user_id']
        tab          = request.args.get('tab', 'stats')
        active_mag_id = request.args.get('mag_id', type=int)
        search_query  = request.args.get('q', '').strip() or None

        conn = get_connection()
        if not conn:
            flash("Không kết nối được database", "danger")
            return render_template(
                "dashboard.html",
                stats={}, articles=[], magazines=[],
                user_email=session['user_email'],
                user_role=session['user_role'],
                active_tab=tab,
                primary_mag_title=None, active_mag_id=None,
                active_magazine=None, admin_users=[], admin_stats={},
            )

        t0 = time.perf_counter()
        try:
            cursor = conn.cursor(dictionary=True)

            t_stats_start = time.perf_counter()
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
                    SUM(CASE WHEN status = 'draft'     THEN 1 ELSE 0 END) as draft,
                    SUM(CASE WHEN status = 'pending'   THEN 1 ELSE 0 END) as pending,
                    SUM(view_count) as total_views
                FROM articles WHERE user_id = %s
                """,
                (user_id,),
            )
            stats   = cursor.fetchone() or {}
            t_stats = time.perf_counter() - t_stats_start

            t_articles_start = time.perf_counter()
            # Bài viết được lazy-load qua AJAX (/dashboard/posts/fragment)
            # Không query ở đây để giảm thời gian load trang
            my_articles = []
            t_articles = time.perf_counter() - t_articles_start

            t_mag_start = time.perf_counter()
            cursor.execute(
                """
                SELECT m.*, COUNT(a.id) as article_count
                FROM magazines m
                LEFT JOIN articles a ON a.magazine_id = m.id
                WHERE m.user_id = %s
                GROUP BY m.id
                ORDER BY m.created_at DESC
                """,
                (user_id,),
            )
            my_magazines = cursor.fetchall() or []
            t_magazines  = time.perf_counter() - t_mag_start

            if not my_magazines:
                cursor.close()
                conn.close()
                return redirect(url_for('create_magazine_page'))

            if not active_mag_id:
                # Ưu tiên tạp chí cuối cùng đã chọn (lưu trong session)
                last_mag_id = session.get('active_mag_id')
                if last_mag_id:
                    ids = [m.get('id') for m in my_magazines if isinstance(m, dict)]
                    if last_mag_id in ids:
                        active_mag_id = last_mag_id
                if not active_mag_id:
                    first = my_magazines[0]
                    active_mag_id = first.get('id') if isinstance(first, dict) else None

            cursor.execute(
                "SELECT * FROM subscription_plans WHERE is_active=1 ORDER BY sort_order, id"
            )
            plans = cursor.fetchall() or []

            cursor.execute(
                """
                SELECT us.*, sp.name AS plan_name, sp.price_monthly, sp.badge_color,
                       sp.magazines_limit, sp.articles_per_day, sp.auto_schedule
                FROM user_subscriptions us
                JOIN subscription_plans sp ON sp.id = us.plan_id
                WHERE us.user_id=%s AND us.status='active'
                  AND (us.end_date IS NULL OR us.end_date >= CURDATE())
                ORDER BY us.end_date DESC LIMIT 1
                """,
                (user_id,),
            )
            active_sub = cursor.fetchone()

            cursor.execute("SELECT token_balance FROM users WHERE id = %s", (user_id,))
            _tok = cursor.fetchone()
            token_balance = int(_tok['token_balance']) if _tok and _tok.get('token_balance') is not None else 5

            admin_users_list = []
            admin_stats = {}
            if session.get('user_role') == 'admin':
                try:
                    cursor.execute(
                        "SELECT COUNT(*) as total_users, "
                        "SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active_users, "
                        "SUM(CASE WHEN is_active=0 THEN 1 ELSE 0 END) as locked_users FROM users"
                    )
                    admin_stats = cursor.fetchone() or {}
                    cursor.execute("SELECT COUNT(*) as total_magazines FROM magazines")
                    r = cursor.fetchone()
                    admin_stats['total_magazines'] = r['total_magazines'] if r else 0
                    cursor.execute("SELECT COUNT(*) as total_articles FROM articles")
                    r = cursor.fetchone()
                    admin_stats['total_articles'] = r['total_articles'] if r else 0
                except Exception as e:
                    print(f"[ERR] admin tab data: {e}")

            cursor.close()
            conn.close()

            primary_mag_title = None
            active_mag = None
            if my_magazines:
                if active_mag_id:
                    for m in my_magazines:
                        if m.get("id") == active_mag_id:
                            active_mag = m
                            break
                if not active_mag:
                    active_mag = my_magazines[0]
                    active_mag_id = active_mag.get("id")
                primary_mag_title = active_mag.get("title")
                # Lưu tạp chí đang active vào session để nhớ cho lần sau
                session['active_mag_id'] = active_mag_id

            total_time = time.perf_counter() - t0
            print(
                f"[PERF] /dashboard stats={t_stats:.3f}s, articles={t_articles:.3f}s, "
                f"magazines={t_magazines:.3f}s, total={total_time:.3f}s"
            )

            # Lấy danh sách lịch tự động (luôn load để tab schedules hiển thị đúng khi switch client-side)
            user_schedules = get_schedules_by_user(user_id)

            return render_template(
                "dashboard.html",
                stats=stats, articles=my_articles, magazines=my_magazines,
                plans=plans, active_sub=active_sub, token_balance=token_balance,
                user_email=session['user_email'], user_role=session['user_role'],
                active_tab=tab, primary_mag_title=primary_mag_title,
                active_mag_id=active_mag_id, active_magazine=active_mag,
                admin_users=admin_users_list, admin_stats=admin_stats,
                user_schedules=user_schedules,
            )
        except Exception as e:
            print(f"[ERR] dashboard: {e}")
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
            flash("Có lỗi khi tải dashboard", "danger")
            return render_template(
                "dashboard.html",
                stats={}, articles=[], magazines=[],
                user_email=session['user_email'], user_role=session['user_role'],
                active_tab=tab, primary_mag_title=None, active_mag_id=None,
                active_magazine=None, admin_users=[], admin_stats={},
            )

    @app.route("/dashboard/save-theme", methods=["POST"])
    @login_required
    def dashboard_save_theme():
        try:
            user_id = session.get("user_id")
            mag_id  = request.form.get("mag_id", type=int)
            theme_input = (request.form.get("theme") or "").strip()
            article_theme_input = (request.form.get("article_theme") or "").strip()

            allowed_themes = {"newsmatic", "default", "moderngrid", "aurora"}
            allowed_article_themes = {"default", "splitview"}

            if theme_input and theme_input not in allowed_themes:
                return jsonify({"ok": False, "message": "Giao diện tạp chí không hợp lệ"})
            if article_theme_input and article_theme_input not in allowed_article_themes:
                return jsonify({"ok": False, "message": "Giao diện bài viết không hợp lệ"})

            if not theme_input and not article_theme_input:
                return jsonify({"ok": False, "message": "Thiếu dữ liệu giao diện"})
            if not mag_id:
                return jsonify({"ok": False, "message": "Thiếu mag_id"})
            magazine = get_magazine_by_id(mag_id)
            if not magazine:
                return jsonify({"ok": False, "message": "Không tìm thấy tạp chí"})
            if int(magazine.get("user_id", 0)) != int(user_id or 0):
                return jsonify({"ok": False, "message": "Không có quyền"})

            theme = theme_input or (magazine.get("theme") or "newsmatic")
            article_theme = article_theme_input or (magazine.get("article_theme") or "default")

            print(f"[DEBUG] save-theme: mag_id={mag_id}, theme='{theme}', article_theme='{article_theme}', user_id={user_id}")
            from database.magazine_model_simple import update_magazine_basic
            ok = update_magazine_basic(
                magazine_id=mag_id,
                title=magazine.get("title") or "",
                slug=magazine.get("slug") or "",
                topic=magazine.get("topic") or "",
                description=magazine.get("description") or "",
                keywords=magazine.get("keywords") or "",
                theme=theme,
                article_theme=article_theme,
            )
            print(f"[DEBUG] save-theme result: ok={ok}")
            return jsonify({"ok": bool(ok), "theme": theme, "article_theme": article_theme})
        except Exception as e:
            print(f"[ERR] dashboard_save_theme: {e}")
            return jsonify({"ok": False, "message": str(e)})

    @app.route("/dashboard/settings/edit", methods=["POST"])
    @login_required
    def dashboard_edit_setting():
        from app.utils.helpers import _slugify
        user_id   = session.get("user_id")
        mag_id    = request.form.get("magazine_id", type=int)
        field     = (request.form.get("field") or "").strip()
        new_value = (request.form.get("value") or "").strip()
        allowed_fields = {"title", "description", "topic", "keywords", "slug"}
        if not mag_id or field not in allowed_fields:
            flash("Yêu cầu chỉnh sửa không hợp lệ.", "error")
            return redirect(url_for("dashboard", tab="settings"))
        magazine = get_magazine_by_id(mag_id)
        if not magazine:
            flash("Tạp chí không tồn tại.", "error")
            return redirect(url_for("dashboard", tab="settings"))
        if magazine.get("user_id") != user_id:
            flash("Bạn không có quyền chỉnh sửa tạp chí này.", "error")
            return redirect(url_for("dashboard", tab="settings", mag_id=mag_id))

        title       = (magazine.get("title") or "").strip()
        description = (magazine.get("description") or "").strip()
        topic       = (magazine.get("topic") or "").strip()
        keywords    = (magazine.get("keywords") or "").strip()
        slug        = (magazine.get("slug") or "").strip() or None
        theme       = (magazine.get("theme") or None)

        try:
            if field == "title":
                if not new_value:
                    flash("Tiêu đề tạp chí không được để trống!", "error")
                    return redirect(url_for("dashboard", tab="settings", mag_id=mag_id))
                title = new_value
            elif field == "description":
                description = new_value
            elif field == "topic":
                topic = new_value
            elif field == "keywords":
                keywords = new_value
            elif field == "slug":
                slug = new_value or None
                if not slug:
                    slug = _slugify(title)
            from database.magazine_model_simple import update_magazine_basic
            ok = update_magazine_basic(
                magazine_id=mag_id,
                title=title, slug=slug, topic=topic,
                description=description, keywords=keywords, theme=theme,
            )
        except Exception as e:
            print(f"[ERR] dashboard_edit_setting: {e}")
            ok = False

        if not ok:
            flash("Không thể lưu cài đặt. Có thể slug đã trùng với tạp chí khác.", "error")
        else:
            flash("Đã cập nhật cài đặt tạp chí.", "success")
        return redirect(url_for("dashboard", tab="settings", mag_id=mag_id))

    @app.route("/dashboard/settings/save", methods=["POST"])
    @login_required
    def dashboard_save_settings():
        """Lưu toàn bộ cài đặt tạp chí từ tab Cài đặt."""
        user_id = session.get("user_id")
        mag_id  = request.form.get("magazine_id", type=int)
        if not mag_id:
            flash("Thiếu thông tin tạp chí.", "error")
            return redirect(url_for("dashboard", tab="settings"))

        magazine = get_magazine_by_id(mag_id)
        if not magazine or magazine.get("user_id") != user_id:
            flash("Tạp chí không tồn tại hoặc bạn không có quyền.", "error")
            return redirect(url_for("dashboard", tab="settings"))

        from app.utils.helpers import _slugify
        title          = (request.form.get("title") or "").strip()
        slug           = (request.form.get("slug") or "").strip()
        custom_domain  = (request.form.get("custom_domain") or "").strip() or None
        language       = request.form.get("language", "vi")
        comments_locked = 1 if request.form.get("comments_locked") else 0
        timezone       = request.form.get("timezone", "Asia/Ho_Chi_Minh")

        if not title:
            flash("Tên tạp chí không được để trống!", "error")
            return redirect(url_for("dashboard", tab="settings", mag_id=mag_id))
        if not slug:
            slug = _slugify(title)

        ok, err = update_magazine_settings(
            magazine_id=mag_id, user_id=user_id,
            title=title, slug=slug,
            custom_domain=custom_domain,
            language=language,
            comments_locked=comments_locked,
            timezone=timezone,
        )
        if not ok:
            flash(err or "Không thể lưu cài đặt. Có thể slug đã trùng.", "error")
        else:
            flash("Đã lưu cài đặt tạp chí.", "success")
        return redirect(url_for("dashboard", tab="settings", mag_id=mag_id))

    @app.route("/dashboard/comments/fragment")
    @login_required
    def dashboard_comments_fragment():
        from database.comment_model_simple import _detect_comments_schema
        user_id   = session['user_id']
        mag_id    = request.args.get('mag_id', type=int)
        filter_by = request.args.get('filter', 'all')  # all | pending | approved
        conn = get_connection()
        comments = []
        total = 0
        if conn and mag_id:
            try:
                cursor = conn.cursor(dictionary=True)
                schema = _detect_comments_schema()
                has_parent_id = schema.get('has_parent_id', False)
                if has_parent_id:
                    base_sql = """
                        SELECT c.id, c.content, c.created_at,
                               u.full_name AS user_name, u.email AS user_email,
                               a.title AS article_title, a.id AS article_id,
                               p.full_name AS reply_to_name,
                               pc.content AS reply_to_content
                        FROM comments c
                        JOIN articles a ON a.id = c.article_id
                        LEFT JOIN users u ON u.id = c.user_id
                        LEFT JOIN comments pc ON pc.id = c.parent_id
                        LEFT JOIN users p ON p.id = pc.user_id
                        WHERE a.magazine_id = %s
                        ORDER BY c.created_at DESC LIMIT 200
                    """
                else:
                    base_sql = """
                        SELECT c.id, c.content, c.created_at,
                               u.full_name AS user_name, u.email AS user_email,
                               a.title AS article_title, a.id AS article_id,
                               NULL AS reply_to_name,
                               NULL AS reply_to_content
                        FROM comments c
                        JOIN articles a ON a.id = c.article_id
                        LEFT JOIN users u ON u.id = c.user_id
                        WHERE a.magazine_id = %s
                        ORDER BY c.created_at DESC LIMIT 200
                    """
                cursor.execute(base_sql, [mag_id])
                comments = cursor.fetchall() or []
                total = len(comments)
                cursor.close()
            except Exception as e:
                print(f"[ERR] dashboard_comments_fragment: {e}")
            finally:
                conn.close()
        from flask import render_template_string
        return render_template_string(
            COMMENTS_FRAGMENT_TMPL,
            comments=comments,
            total=total,
            mag_id=mag_id,
            filter_by=filter_by,
        )

    @app.route("/dashboard/comments/<int:comment_id>/delete", methods=["POST"])
    @login_required
    def dashboard_delete_comment(comment_id):
        user_id = session['user_id']
        mag_id  = request.form.get('mag_id', type=int)
        conn = get_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                # Chỉ được xóa nếu comment thuộc bài của user này
                cursor.execute(
                    """
                    SELECT c.id FROM comments c
                    JOIN articles a ON a.id = c.article_id
                    WHERE c.id = %s AND a.user_id = %s
                    """,
                    (comment_id, user_id),
                )
                if cursor.fetchone():
                    cursor.execute("DELETE FROM comments WHERE id = %s", (comment_id,))
                    conn.commit()
                cursor.close()
            except Exception as e:
                print(f"[ERR] delete_comment: {e}")
            finally:
                conn.close()
        from flask import jsonify
        return jsonify({"ok": True})


COMMENTS_FRAGMENT_TMPL = """
<style>
.cmt-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.4rem;}
.cmt-filter-wrap{position:relative;display:inline-block;}
.cmt-filter{appearance:none;-webkit-appearance:none;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:.45rem 2rem .45rem .85rem;font-size:.86rem;color:#374151;cursor:pointer;font-weight:600;}
.cmt-filter-arrow{position:absolute;right:.6rem;top:50%;transform:translateY(-50%);pointer-events:none;color:#9ca3af;}
.cmt-manage-btn{font-size:.8rem;font-weight:700;color:#0891b2;letter-spacing:.5px;background:none;border:none;cursor:pointer;text-transform:uppercase;}
.cmt-list{display:flex;flex-direction:column;gap:.85rem;}
.cmt-card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:1rem 1.2rem;display:flex;gap:.9rem;align-items:flex-start;transition:box-shadow .15s;}
.cmt-card:hover{box-shadow:0 4px 14px rgba(0,0,0,.07);}
.cmt-avatar{width:40px;height:40px;min-width:40px;border-radius:50%;background:#bfdbfe;display:flex;align-items:center;justify-content:center;font-size:1.1rem;color:#1d4ed8;font-weight:700;}
.cmt-body{flex:1;min-width:0;}
.cmt-meta{font-size:.83rem;color:#6b7280;margin-bottom:.25rem;}
.cmt-meta strong{color:#111827;font-weight:600;}
.cmt-meta a{color:#0369a1;text-decoration:none;font-weight:500;}
.cmt-meta a:hover{text-decoration:underline;}
.cmt-text{font-size:.9rem;color:#374151;margin:.2rem 0 .4rem;word-break:break-word;}
.cmt-reply-hint{font-size:.78rem;color:#6b7280;font-style:italic;}
.cmt-reply-hint strong{color:#374151;}
.cmt-date{font-size:.78rem;color:#9ca3af;white-space:nowrap;margin-left:auto;}
.cmt-del-btn{background:none;border:none;cursor:pointer;color:#d1d5db;font-size:.92rem;padding:.15rem .3rem;border-radius:4px;transition:color .15s;}
.cmt-del-btn:hover{color:#ef4444;}
.cmt-empty{text-align:center;padding:3rem 1rem;color:#9ca3af;font-size:.9rem;}
</style>
<div class="cmt-header">
    <div class="cmt-filter-wrap">
        <select class="cmt-filter" id="cmtFilter" onchange="cmtApplyFilter(this.value)">
            <option value="all" {% if filter_by=='all' %}selected{% endif %}>Tất cả ({{ total }})</option>
        </select>
        <span class="cmt-filter-arrow">▾</span>
    </div>
    <button class="cmt-manage-btn" onclick="cmtSelectAll()">Quản lý</button>
</div>
{% if comments %}
<div class="cmt-list" id="cmtList">
{% for c in comments %}
<div class="cmt-card" id="cmtCard{{ c.id }}">
    <div class="cmt-avatar">{{ (c.user_name or c.user_email or '?')[0]|upper }}</div>
    <div class="cmt-body">
        <div class="cmt-meta">
            <strong>{{ c.user_name or c.user_email or 'Ẩn danh' }}</strong>
            đã nhận xét về
            <a href="/article/{{ c.article_id }}" class="cmt-article-link">"{{ c.article_title }}"</a>
            {% if c.reply_to_name %}
            &nbsp;·&nbsp;<span>Phản hồi <a href="#">một nhận xét</a> của <strong>{{ c.reply_to_name }}</strong></span>
            {% endif %}
        </div>
        <div class="cmt-text">{{ c.content }}</div>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:.3rem;min-width:80px;">
        <span class="cmt-date">{{ c.created_at.strftime('%d thg %m, %Y') if c.created_at else '' }}</span>
        <button class="cmt-del-btn" title="Xóa nhận xét"
            onclick="cmtDelete({{ c.id }}, {{ mag_id or 0 }}, this)">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
            </svg>
        </button>
    </div>
</div>
{% endfor %}
</div>
{% else %}
<div class="cmt-empty">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" style="width:40px;height:40px;fill:#d1d5db;display:block;margin:0 auto .7rem;"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>
    Chưa có nhận xét nào cho tạp chí này.
</div>
{% endif %}
<script>
function cmtApplyFilter(val) {
    // placeholder for future filter logic
}
function cmtSelectAll() {
    // placeholder for bulk actions
}
function cmtDelete(commentId, magId, btn) {
    if (!confirm('Xóa nhận xét này?')) return;
    var card = document.getElementById('cmtCard' + commentId);
    fetch('/dashboard/comments/' + commentId + '/delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'mag_id=' + magId
    }).then(function(r){ return r.json(); }).then(function(d){
        if (d.ok && card) {
            card.style.transition = 'opacity .3s';
            card.style.opacity = '0';
            setTimeout(function(){ card.remove(); }, 300);
        }
    });
}
</script>
"""
