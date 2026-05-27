"""
Mobile JSON API routes – dùng cho Flutter app.
Tất cả endpoint đều trả JSON, xác thực qua session cookie.
"""
from flask import session, request, jsonify

from database.user_model_simple import (
    create_user, verify_user, get_user_by_id, get_user_token_balance,
    get_user_by_email,
)
from database.magazine_model_simple import (
    get_all_magazines, get_magazine_by_id, get_article_previews_by_magazine,
)
from database.article_model_simple import (
    get_article_by_id, get_top_view_articles, search_articles,
)


def _article_preview(a: dict) -> dict:
    imgs = a.get("image_urls")
    thumb = None
    if isinstance(imgs, list) and imgs:
        thumb = imgs[0] or None
    elif isinstance(imgs, str) and imgs.startswith("["):
        import json
        try:
            parsed = json.loads(imgs)
            thumb = parsed[0] if parsed else None
        except Exception:
            pass
    return {
        "id":         a.get("id"),
        "title":      a.get("title", ""),
        "summary":    a.get("summary") or a.get("description", ""),
        "thumbnail":  thumb,
        "category":   a.get("topic_name", ""),
        "created_at": str(a.get("created_at", "")),
        "view_count": a.get("view_count", 0),
        "magazine_id": a.get("magazine_id"),
    }


def register_routes(app):

    # ------------------------------------------------------------------ #
    # Auth                                                                 #
    # ------------------------------------------------------------------ #

    @app.route("/api/login", methods=["POST"])
    def api_login():
        data = request.get_json(silent=True) or {}
        email    = (data.get("email") or "").strip()
        password = data.get("password") or ""
        if not email or not password:
            return jsonify({"ok": False, "error": "Email và mật khẩu không được để trống"}), 400
        user = verify_user(email, password)
        if not user:
            return jsonify({"ok": False, "error": "Email hoặc mật khẩu không đúng"}), 401
        session["user_id"]    = user["id"]
        session["user_email"] = user["email"]
        session["user_role"]  = user.get("role", "user")
        return jsonify({
            "ok": True,
            "user": {
                "id":    user["id"],
                "email": user["email"],
                "role":  user.get("role", "user"),
                "name":  user.get("full_name") or user.get("display_name") or email.split("@")[0],
            },
        })

    @app.route("/api/register", methods=["POST"])
    def api_register():
        data = request.get_json(silent=True) or {}
        email     = (data.get("email") or "").strip()
        password  = data.get("password") or ""
        full_name = (data.get("full_name") or "").strip()
        if not email or not password:
            return jsonify({"ok": False, "error": "Email và mật khẩu không được để trống"}), 400
        if len(password) < 6:
            return jsonify({"ok": False, "error": "Mật khẩu phải có ít nhất 6 ký tự"}), 400
        user_id = create_user(email, password, "user", full_name)
        if not user_id:
            return jsonify({"ok": False, "error": "Email đã được sử dụng"}), 409
        return jsonify({"ok": True, "user_id": user_id}), 201

    @app.route("/api/logout", methods=["POST"])
    def api_logout():
        session.clear()
        return jsonify({"ok": True})

    @app.route("/api/auth/google", methods=["POST"])
    def api_google_auth():
        """Xác thực Google ID token từ Flutter app."""
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as grequests
        except ImportError:
            return jsonify({"ok": False,
                            "error": "google-auth chưa được cài đặt trên server"}), 500

        data = request.get_json(silent=True) or {}
        token = data.get("id_token", "").strip()
        if not token:
            return jsonify({"ok": False, "error": "Thiếu id_token"}), 400

        try:
            idinfo = id_token.verify_oauth2_token(
                token,
                grequests.Request(),
                clock_skew_in_seconds=10,
            )
        except ValueError as e:
            return jsonify({"ok": False, "error": f"Token không hợp lệ: {e}"}), 401

        email      = idinfo.get("email", "")
        name       = idinfo.get("name", email.split("@")[0])
        picture    = idinfo.get("picture", "")

        if not email:
            return jsonify({"ok": False, "error": "Không lấy được email từ Google"}), 400

        # Tìm hoặc tạo user
        user = get_user_by_email(email)
        if not user:
            # Tạo tài khoản mới với random password (không dùng để login thường)
            import secrets
            rand_pass = secrets.token_hex(16)
            user_id = create_user(email, rand_pass, "user", name)
            if not user_id:
                return jsonify({"ok": False,
                                "error": "Không thể tạo tài khoản"}), 500
            user = get_user_by_id(user_id)

        session["user_id"]    = user["id"]
        session["user_email"] = user["email"]
        session["user_role"]  = user.get("role", "user")
        return jsonify({
            "ok": True,
            "user": {
                "id":      user["id"],
                "email":   user["email"],
                "role":    user.get("role", "user"),
                "name":    user.get("full_name") or name,
                "picture": picture,
            },
        })

    @app.route("/api/me")
    def api_me():
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        user = get_user_by_id(user_id)
        if not user:
            return jsonify({"ok": False, "error": "Không tìm thấy người dùng"}), 404
        return jsonify({
            "ok": True,
            "user": {
                "id":     user["id"],
                "email":  user["email"],
                "role":   user.get("role", "user"),
                "name":   user.get("full_name") or user.get("display_name") or user["email"].split("@")[0],
                "tokens": get_user_token_balance(user_id),
            },
        })

    # ------------------------------------------------------------------ #
    # Magazines                                                            #
    # ------------------------------------------------------------------ #

    @app.route("/api/magazines")
    def api_magazines():
        magazines = get_all_magazines(limit=50) or []
        result = []
        for m in magazines:
            result.append({
                "id":            m.get("id"),
                "name":          m.get("name", ""),
                "description":   m.get("description", ""),
                "slug":          m.get("slug", ""),
                "cover_image":   m.get("cover_image") or "",
                "article_count": m.get("article_count", 0),
            })
        return jsonify({"ok": True, "magazines": result})

    @app.route("/api/magazine/<int:magazine_id>")
    def api_magazine_detail(magazine_id):
        magazine = get_magazine_by_id(magazine_id)
        if not magazine:
            return jsonify({"ok": False, "error": "Tạp chí không tồn tại"}), 404
        articles = get_article_previews_by_magazine(magazine_id, limit=30) or []
        return jsonify({
            "ok": True,
            "magazine": {
                "id":            magazine.get("id"),
                "name":          magazine.get("name", ""),
                "description":   magazine.get("description", ""),
                "cover_image":   magazine.get("cover_image") or "",
                "article_count": magazine.get("article_count", 0),
            },
            "articles": [_article_preview(a) for a in articles],
        })

    # ------------------------------------------------------------------ #
    # Articles                                                             #
    # ------------------------------------------------------------------ #

    @app.route("/api/article/<int:article_id>")
    def mobile_api_article_detail(article_id):
        article = get_article_by_id(article_id)
        if not article:
            return jsonify({"ok": False, "error": "Bài viết không tồn tại"}), 404
        if article.get("status") != "published":
            uid = session.get("user_id")
            if not uid or (uid != article.get("user_id")):
                return jsonify({"ok": False, "error": "Bài viết chưa được xuất bản"}), 403
        imgs = article.get("image_urls")
        thumb = None
        if isinstance(imgs, list) and imgs:
            thumb = imgs[0] or None
        elif isinstance(imgs, str) and imgs.startswith("["):
            import json as _j
            try:
                parsed = _j.loads(imgs)
                thumb = parsed[0] if parsed else None
            except Exception:
                pass
        return jsonify({
            "ok": True,
            "article": {
                "id":          article.get("id"),
                "title":       article.get("title", ""),
                "content":     article.get("content", ""),
                "summary":     article.get("summary", ""),
                "thumbnail":   thumb,
                "category":    article.get("topic_name", ""),
                "magazine_id": article.get("magazine_id"),
                "created_at":  str(article.get("created_at", "")),
                "view_count":  article.get("view_count", 0),
            },
        })

    @app.route("/api/articles/trending")
    def api_trending_articles():
        articles = get_top_view_articles(limit=10) or []
        return jsonify({"ok": True, "articles": [_article_preview(a) for a in articles]})

    @app.route("/api/search")
    def api_search():
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"ok": True, "results": []})
        results = search_articles(q, limit=20) or []
        return jsonify({"ok": True, "results": [_article_preview(a) for a in results]})

    # ------------------------------------------------------------------ #
    # My Magazines                                                         #
    # ------------------------------------------------------------------ #

    @app.route("/api/my-magazines")
    def api_my_magazines():
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        from database.magazine_model_simple import get_magazines_by_user
        magazines = get_magazines_by_user(user_id) or []
        result = []
        for m in magazines:
            result.append({
                "id":            m.get("id"),
                "name":          m.get("name", ""),
                "description":   m.get("description", ""),
                "slug":          m.get("slug", ""),
                "cover_image":   m.get("cover_image") or "",
                "article_count": m.get("article_count", 0),
                "status":        m.get("status", "active"),
            })
        return jsonify({"ok": True, "magazines": result})

    @app.route("/api/magazine/create", methods=["POST"])
    def api_create_magazine():
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        data  = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        categories  = data.get("categories") or []

        if not title:
            return jsonify({"ok": False, "error": "Tên tạp chí không được để trống"}), 400

        balance = get_user_token_balance(user_id)
        if balance < 2:
            return jsonify({"ok": False,
                            "error": f"Cần ít nhất 2 Token để tạo tạp chí. Còn {balance} Token."}), 400

        import re as _re, json as _json2
        def _mobile_slugify(s):
            import unicodedata
            replacements = {
                'à':'a','á':'a','ạ':'a','ả':'a','ã':'a','â':'a','ầ':'a','ấ':'a',
                'ậ':'a','ẩ':'a','ẫ':'a','ă':'a','ằ':'a','ắ':'a','ặ':'a','ẳ':'a','ẵ':'a',
                'è':'e','é':'e','ẹ':'e','ẻ':'e','ẽ':'e','ê':'e','ề':'e','ế':'e',
                'ệ':'e','ể':'e','ễ':'e','ì':'i','í':'i','ị':'i','ỉ':'i','ĩ':'i',
                'ò':'o','ó':'o','ọ':'o','ỏ':'o','õ':'o','ô':'o','ồ':'o','ố':'o',
                'ộ':'o','ổ':'o','ỗ':'o','ơ':'o','ờ':'o','ớ':'o','ợ':'o','ở':'o','ỡ':'o',
                'ù':'u','ú':'u','ụ':'u','ủ':'u','ũ':'u','ư':'u','ừ':'u','ứ':'u',
                'ự':'u','ử':'u','ữ':'u','ỳ':'y','ý':'y','ỵ':'y','ỷ':'y','ỹ':'y','đ':'d',
            }
            s = s.lower().strip()
            for k, v in replacements.items():
                s = s.replace(k, v)
            s = _re.sub(r'[^a-z0-9]+', '-', s)
            s = _re.sub(r'^-+|-+$', '', s)
            return s

        slug = _mobile_slugify(title)

        categories_config = []
        num_articles = 0
        for cat in categories:
            name  = (cat.get("name") or "").strip()
            count = max(1, int(cat.get("count") or 1))
            kw    = (cat.get("keywords") or "").strip()
            if name:
                cfg = {"name": name, "article_count": count}
                if kw:
                    cfg["keywords"] = kw
                categories_config.append(cfg)
                num_articles += count

        topic    = categories_config[0]["name"] if categories_config else title
        keywords = ", ".join(c.get("name", "") for c in categories_config)

        from database.magazine_model_simple import create_magazine as _create_mag
        magazine_id = _create_mag(
            user_id=user_id,
            title=title, slug=slug, topic=topic, keywords=keywords,
            description=description or title,
            num_articles=num_articles,
            categories_config=categories_config,
        )
        if not magazine_id:
            return jsonify({"ok": False, "error": "Không thể tạo tạp chí (slug có thể đã tồn tại)"}), 500

        from database.user_model_simple import deduct_tokens
        deduct_tokens(user_id, 2)
        return jsonify({"ok": True, "magazine_id": magazine_id}), 201

    @app.route("/api/magazine/<int:magazine_id>/delete", methods=["POST"])
    def api_delete_magazine(magazine_id):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        from database.magazine_model_simple import delete_magazine as _del_mag
        ok = _del_mag(magazine_id, user_id)
        if ok:
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "Không thể xóa tạp chí"}), 400

    # ------------------------------------------------------------------ #
    # Comments                                                             #
    # ------------------------------------------------------------------ #

    @app.route("/api/article/<int:article_id>/comments")
    def api_get_comments(article_id):
        from database.comment_model_simple import get_comments_by_article
        comments = get_comments_by_article(article_id, user_id=session.get("user_id")) or []
        result = []
        for c in comments:
            result.append({
                "id":         c.get("id"),
                "user_name":  c.get("user_name") or c.get("user_email", "Ẩn danh"),
                "content":    c.get("content", ""),
                "created_at": (
                    c.get("created_at").strftime("%d/%m/%Y %H:%M")
                    if hasattr(c.get("created_at"), "strftime")
                    else str(c.get("created_at", ""))
                ),
                "likes":      c.get("likes", 0),
            })
        return jsonify({"ok": True, "comments": result})

    @app.route("/api/article/<int:article_id>/comment", methods=["POST"])
    def api_add_comment(article_id):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        data    = request.get_json(silent=True) or {}
        content = (data.get("content") or "").strip()
        if not content:
            return jsonify({"ok": False, "error": "Nội dung bình luận không được để trống"}), 400
        from database.comment_model_simple import add_comment as _add_cmt
        cmt_id = _add_cmt(article_id, user_id, content)
        if cmt_id:
            return jsonify({"ok": True, "comment_id": cmt_id}), 201
        return jsonify({"ok": False, "error": "Không thể thêm bình luận"}), 500

    @app.route("/api/comment/<int:comment_id>/like", methods=["POST"])
    def api_like_comment_mobile(comment_id):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        from database.comment_model_simple import like_comment as _like
        result = _like(comment_id, user_id)
        if result:
            return jsonify({"ok": True, **result})
        return jsonify({"ok": False, "error": "Không thể like bình luận"}), 400

    # ------------------------------------------------------------------ #
    # Related Articles                                                     #
    # ------------------------------------------------------------------ #

    @app.route("/api/article/<int:article_id>/related")
    def api_related_articles(article_id):
        article = get_article_by_id(article_id)
        if not article:
            return jsonify({"ok": True, "articles": []})
        topic = article.get("topic") or article.get("topic_name") or ""
        related = []
        if topic:
            from database.article_model_simple import get_related_articles
            related = get_related_articles(topic=topic, exclude_id=article_id, limit=4) or []
        return jsonify({"ok": True, "articles": [_article_preview(a) for a in related]})

    # ------------------------------------------------------------------ #
    # Plans                                                                #
    # ------------------------------------------------------------------ #

    @app.route("/api/plans")
    def api_plans():
        plans = [
            {
                "id": 1, "name": "Starter", "tokens": 10,
                "price": "50.000đ", "price_number": 50000,
                "features": ["10 Token", "Tạo ~5 tạp chí", "Hỗ trợ cơ bản"],
                "popular": False,
            },
            {
                "id": 2, "name": "Pro", "tokens": 30,
                "price": "120.000đ", "price_number": 120000,
                "features": ["30 Token", "Không giới hạn tạp chí", "Lịch tự động", "Ưu tiên hỗ trợ"],
                "popular": True,
            },
            {
                "id": 3, "name": "Business", "tokens": 100,
                "price": "350.000đ", "price_number": 350000,
                "features": ["100 Token", "Không giới hạn tất cả", "Lịch tự động", "Hỗ trợ 24/7"],
                "popular": False,
            },
        ]
        return jsonify({"ok": True, "plans": plans})

    # ------------------------------------------------------------------ #
    # Schedules                                                            #
    # ------------------------------------------------------------------ #

    @app.route("/api/my-schedules")
    def api_my_schedules():
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        from database.magazine_model_simple import get_magazines_by_user as _get_mags
        from database.schedule_model_simple import get_schedules_by_magazine as _get_scheds
        magazines = _get_mags(user_id) or []
        all_schedules = []
        for mag in magazines:
            scheds = _get_scheds(mag["id"]) or []
            for s in scheds:
                all_schedules.append({
                    "id":               s.get("id"),
                    "magazine_id":      s.get("magazine_id"),
                    "magazine_name":    mag.get("name", ""),
                    "frequency":        s.get("frequency", "daily"),
                    "hour":             s.get("hour", 8),
                    "minute":           s.get("minute", 0),
                    "num_articles":     s.get("num_articles", 1),
                    "category_name":    s.get("category_name", ""),
                    "days_of_week":     s.get("days_of_week") or "",
                    "interval_minutes": s.get("interval_minutes", 0),
                    "is_active":        bool(s.get("is_active")),
                    "keywords":         s.get("keywords") or "",
                })
        return jsonify({"ok": True, "schedules": all_schedules})

    @app.route("/api/magazine/<int:magazine_id>/schedules")
    def api_magazine_schedules(magazine_id):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        from database.schedule_model_simple import get_schedules_by_magazine as _get_scheds
        scheds = _get_scheds(magazine_id) or []
        result = []
        for s in scheds:
            result.append({
                "id":               s.get("id"),
                "magazine_id":      s.get("magazine_id"),
                "frequency":        s.get("frequency", "daily"),
                "hour":             s.get("hour", 8),
                "minute":           s.get("minute", 0),
                "num_articles":     s.get("num_articles", 1),
                "category_name":    s.get("category_name", ""),
                "days_of_week":     s.get("days_of_week") or "",
                "interval_minutes": s.get("interval_minutes", 0),
                "is_active":        bool(s.get("is_active")),
                "keywords":         s.get("keywords") or "",
            })
        return jsonify({"ok": True, "schedules": result})

    @app.route("/api/schedule/create", methods=["POST"])
    def api_create_schedule():
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        data          = request.get_json(silent=True) or {}
        magazine_id   = data.get("magazine_id")
        category_name = (data.get("category_name") or "").strip()
        frequency     = data.get("frequency", "daily")
        hour          = int(data.get("hour", 8))
        minute        = int(data.get("minute", 0))
        num_articles  = max(1, int(data.get("num_articles", 1)))
        if not magazine_id or not category_name:
            return jsonify({"ok": False, "error": "Thiếu thông tin bắt buộc"}), 400
        from database.schedule_model_simple import create_schedule as _create_sched
        sched_id = _create_sched(
            magazine_id=magazine_id, user_id=user_id,
            frequency=frequency, hour=hour, minute=minute,
            num_articles=num_articles, category_name=category_name,
        )
        if sched_id:
            return jsonify({"ok": True, "schedule_id": sched_id}), 201
        return jsonify({"ok": False, "error": "Không thể tạo lịch"}), 500

    @app.route("/api/schedule/<int:schedule_id>/toggle", methods=["POST"])
    def api_toggle_schedule(schedule_id):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        from database.schedule_model_simple import (
            toggle_schedule as _toggle, get_schedule_by_id as _get_sched
        )
        s = _get_sched(schedule_id)
        if not s or s.get("user_id") != user_id:
            return jsonify({"ok": False, "error": "Không có quyền"}), 403
        _toggle(schedule_id, user_id)
        updated = _get_sched(schedule_id)
        return jsonify({"ok": True, "is_active": bool((updated or {}).get("is_active"))})

    @app.route("/api/schedule/<int:schedule_id>/delete", methods=["POST"])
    def api_delete_schedule(schedule_id):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"ok": False, "error": "Chưa đăng nhập"}), 401
        from database.schedule_model_simple import (
            delete_schedule as _del_sched, get_schedule_by_id as _get_sched
        )
        s = _get_sched(schedule_id)
        if not s or s.get("user_id") != user_id:
            return jsonify({"ok": False, "error": "Không có quyền"}), 403
        _del_sched(schedule_id, user_id)
        return jsonify({"ok": True})
