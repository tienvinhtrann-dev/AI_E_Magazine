"""
Magazine routes: create, view, settings, generate-more, delete.
Schedule routes: create, toggle, delete schedule.
"""
import json
from flask import session, flash, redirect, url_for, render_template, request, jsonify, make_response

from app.utils.decorators import login_required
from app.utils.helpers import (
    _slugify, _refresh_magazine_category_counts,
    _derive_topic_keywords_from_description, fromjson_filter,
)
from app.extensions import article_generator
from app.services.scheduler_service import _register_schedule_job
from database.magazine_model_simple import (
    create_magazine, get_magazine_by_id, get_magazines_by_user,
    get_articles_by_magazine, get_article_previews_by_magazine, save_article_to_magazine,
    delete_magazine, ensure_magazines_schema,
    get_magazine_by_slug, is_magazine_slug_taken, get_article_topic_counts_by_magazine,
)
from database.schedule_model_simple import (
    create_schedule, get_schedules_by_magazine,
    toggle_schedule, delete_schedule, get_schedule_by_id,
)
from database.user_model_simple import (
    update_user_display_name, get_user_token_balance, deduct_tokens,
)


INITIAL_MAGAZINE_PREVIEW_LIMIT = 12
MAGAZINE_PREVIEW_BATCH_SIZE = 24


def _parse_magazine_categories(magazine):
    categories = []
    categories_raw = magazine.get('categories_config') if isinstance(magazine, dict) else None
    if not categories_raw:
        return categories
    try:
        parsed = json.loads(categories_raw)
    except Exception:
        return categories
    if not isinstance(parsed, list):
        return categories
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name', '')).strip()
        if name:
            categories.append(name)
    return categories


def _resolve_article_category(topic_name, configured_categories):
    topic_name = str(topic_name or '').strip()
    if not topic_name:
        return ''
    if not configured_categories:
        return topic_name

    topic_key = topic_name.lower()
    configured_index = {name.lower(): name for name in configured_categories}
    if topic_key in configured_index:
        return configured_index[topic_key]

    matches = [
        name for name in configured_categories
        if name.lower() in topic_key or topic_key in name.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if matches:
        return matches[0]
    return topic_name


def _extract_preview_image(article):
    imgs = article.get('image_urls') if isinstance(article, dict) else None
    if isinstance(imgs, list) and imgs and imgs[0]:
        image_url = str(imgs[0])
    elif isinstance(imgs, str) and imgs.startswith('http'):
        image_url = imgs
    else:
        image_url = ''
    return image_url if image_url.startswith('http') else ''


def _decorate_preview_articles(articles, configured_categories):
    for article in articles:
        article['_cat'] = _resolve_article_category(article.get('topic'), configured_categories)
        article['_img'] = _extract_preview_image(article)
    return articles


def _build_categories_menu(magazine, topic_counts):
    configured_categories = _parse_magazine_categories(magazine)
    counts = {}
    for row in topic_counts or []:
        topic_name = str((row or {}).get('topic_name') or '').strip()
        article_count = int((row or {}).get('article_count') or 0)
        if article_count <= 0:
            continue
        resolved_name = _resolve_article_category(topic_name, configured_categories)
        if not resolved_name:
            continue
        key = resolved_name.lower()
        if key not in counts:
            counts[key] = {'name': resolved_name, 'article_count': 0}
        counts[key]['article_count'] += article_count

    categories_menu = [
        {'name': name, 'article_count': counts.get(name.lower(), {}).get('article_count', 0)}
        for name in configured_categories
    ]
    existing_keys = {item['name'].strip().lower() for item in categories_menu if item.get('name')}
    for key, payload in counts.items():
        if key not in existing_keys:
            categories_menu.append(payload)

    return categories_menu, configured_categories


def _serialize_preview_article(article):
    created_at = article.get('created_at')
    if hasattr(created_at, 'strftime'):
        created_at_label = created_at.strftime('%d/%m/%Y')
    elif created_at:
        created_at_label = str(created_at)
    else:
        created_at_label = ''

    return {
        'id': article.get('id'),
        'title': article.get('title', ''),
        'summary': article.get('summary', ''),
        'topic': article.get('topic', ''),
        'category': article.get('_cat', ''),
        'image_url': article.get('_img', ''),
        'created_at': created_at_label,
        'view_count': article.get('view_count', 0),
    }


def register_routes(app):

    # ------------------------------------------------------------------
    # Create magazine
    # ------------------------------------------------------------------

    @app.route("/magazine/create", methods=["GET", "POST"])
    @login_required
    def create_magazine_page():
        user_id = session['user_id']
        if request.method == "POST":
            title             = request.form.get("title", "").strip()
            slug_input        = request.form.get("slug", "").strip()
            display_name      = request.form.get("display_name", "").strip()
            combined_desc     = request.form.get("description", "").strip()
            category_names    = request.form.getlist("category_name[]")
            category_counts   = request.form.getlist("category_count[]")
            category_keywords = request.form.getlist("category_keywords[]")

            current_balance = get_user_token_balance(user_id)
            if current_balance < 2:
                flash(
                    "Bạn cần ít nhất 2 Token để tạo tạp chí mới. "
                    "Vui lòng mua thêm Token tại mục Gói dịch vụ.",
                    "error",
                )
                return redirect(url_for('dashboard', tab='plans'))

            categories_config = []
            num_articles = 0
            for idx, raw_name in enumerate(category_names):
                name = (raw_name or '').strip()
                if not name:
                    continue
                count_raw = category_counts[idx] if idx < len(category_counts) else "1"
                try:
                    article_count = int(count_raw)
                except (TypeError, ValueError):
                    article_count = 1
                if article_count < 1:
                    article_count = 1
                cat_keywords = ""
                if idx < len(category_keywords):
                    cat_keywords = (category_keywords[idx] or "").strip()
                cat_cfg = {'name': name, 'article_count': article_count}
                if cat_keywords:
                    cat_cfg['keywords'] = cat_keywords
                categories_config.append(cat_cfg)
                num_articles += article_count

            print("[DEBUG create_magazine] title=", repr(title))
            print("[DEBUG create_magazine] description=", repr(combined_desc))
            print("[DEBUG create_magazine] categories=", categories_config)

            if not title:
                title = "Tạp chí không tên"
            if not combined_desc:
                combined_desc = "Mô tả trống"
            if not categories_config:
                categories_config = []
                num_articles = 0

            if not slug_input:
                slug = _slugify(title)
            else:
                slug = _slugify(slug_input)

            if slug and is_magazine_slug_taken(slug):
                flash("Địa chỉ tạp chí này đã được sử dụng, vui lòng chọn tên khác!", "error")
                return render_template(
                    "magazine_create.html",
                    user_email=session['user_email'],
                    user_role=session.get('user_role'),
                )

            try:
                if display_name:
                    if update_user_display_name(user_id, display_name):
                        session['full_name'] = display_name
            except Exception:
                pass

            topic, keywords, description = _derive_topic_keywords_from_description(
                combined_desc, default_topic=title, default_keywords=""
            )
            if categories_config and not topic:
                topic = categories_config[0]['name']

            magazine_id = create_magazine(
                user_id=user_id,
                title=title, slug=slug, topic=topic, keywords=keywords,
                description=description, num_articles=num_articles,
                categories_config=categories_config,
            )
            if not magazine_id:
                flash("Lỗi khi tạo tạp chí, vui lòng thử lại!", "error")
                return render_template(
                    "magazine_create.html",
                    user_email=session['user_email'],
                    user_role=session.get('user_role'),
                )

            new_balance = deduct_tokens(user_id, 2)
            if new_balance is not None:
                session['token_balance'] = new_balance

            return redirect(url_for('dashboard'))

        return render_template(
            "magazine_create.html",
            user_email=session['user_email'],
            user_role=session.get('user_role'),
        )

    # ------------------------------------------------------------------
    # View magazine
    # ------------------------------------------------------------------

    @app.route("/magazine/<int:magazine_id>")
    def view_magazine(magazine_id):
        magazine = get_magazine_by_id(magazine_id)
        if not magazine:
            flash("Tạp chí không tồn tại!", "error")
            return redirect("/dashboard")

        total_articles = int(magazine.get('article_count') or 0)
        articles = get_article_previews_by_magazine(
            magazine_id,
            limit=INITIAL_MAGAZINE_PREVIEW_LIMIT,
            offset=0,
        )
        topic_counts = get_article_topic_counts_by_magazine(magazine_id)
        selected_category = request.args.get('category', '').strip()
        categories_menu, configured_categories = _build_categories_menu(magazine, topic_counts)
        _decorate_preview_articles(articles, configured_categories)
        is_owner = ('user_id' in session and session['user_id'] == magazine['user_id'])
        response = make_response(render_template(
            "magazine_detail.html",
            magazine=magazine, articles=articles,
            total_articles=total_articles,
            initial_articles_count=len(articles),
            has_more_articles=total_articles > len(articles),
            article_batch_size=MAGAZINE_PREVIEW_BATCH_SIZE,
            categories_menu=categories_menu,
            selected_category=selected_category,
            is_owner=is_owner,
            user_email=session.get('user_email'),
            user_role=session.get('user_role'),
        ))
        # Cache 30s để navigation tức thì; stale-while-revalidate cho phép dùng cache cũ khi revalidate ngầm
        response.headers['Cache-Control'] = 'private, max-age=30, stale-while-revalidate=60'
        return response

    @app.route("/api/magazine/<int:magazine_id>/previews")
    def magazine_article_previews_api(magazine_id):
        magazine = get_magazine_by_id(magazine_id)
        if not magazine:
            return jsonify({'ok': False, 'error': 'Tạp chí không tồn tại'}), 404

        offset = request.args.get('offset', default=0, type=int) or 0
        limit = request.args.get('limit', default=MAGAZINE_PREVIEW_BATCH_SIZE, type=int) or MAGAZINE_PREVIEW_BATCH_SIZE
        offset = max(offset, 0)
        limit = max(1, min(limit, 60))

        configured_categories = _parse_magazine_categories(magazine)
        articles = get_article_previews_by_magazine(magazine_id, limit=limit, offset=offset)
        _decorate_preview_articles(articles, configured_categories)
        total_articles = int(magazine.get('article_count') or 0)

        return jsonify({
            'ok': True,
            'items': [_serialize_preview_article(article) for article in articles],
            'offset': offset,
            'limit': limit,
            'returned': len(articles),
            'total': total_articles,
            'has_more': (offset + len(articles)) < total_articles,
        })

    @app.route("/api/check-magazine-slug")
    @login_required
    def api_check_magazine_slug():
        raw = request.args.get("slug", "").strip()
        if not raw:
            return jsonify({"ok": False, "available": False, "message": "Vui lòng nhập địa chỉ tạp chí"}), 400
        slug = _slugify(raw)
        if not slug:
            return jsonify({"ok": False, "available": False, "message": "Địa chỉ không hợp lệ"}), 400
        taken = is_magazine_slug_taken(slug)
        if taken:
            return jsonify({"ok": True, "available": False, "slug": slug,
                            "message": "Rất tiếc, địa chỉ tạp chí này đã được sử dụng."})
        return jsonify({"ok": True, "available": True, "slug": slug,
                        "message": "Địa chỉ tạp chí này đang hoạt động (có thể sử dụng)."})

    @app.route("/magazine/<slug>")
    def view_magazine_by_slug(slug):
        magazine = get_magazine_by_slug(slug)
        if not magazine and slug.isdigit():
            try:
                magazine = get_magazine_by_id(int(slug))
            except Exception:
                magazine = None
        if not magazine:
            flash("Tạp chí không tồn tại!", "error")
            return redirect("/dashboard")
        return view_magazine(magazine['id'])

    @app.route("/magazine/<magazine_slug>/<article_slug>", methods=["GET", "POST"])
    def view_magazine_article(magazine_slug, article_slug):
        # 1. Look up magazine by slug or ID
        magazine = get_magazine_by_slug(magazine_slug)
        if not magazine and magazine_slug.isdigit():
            try:
                magazine = get_magazine_by_id(int(magazine_slug))
            except Exception:
                magazine = None
        if not magazine:
            flash("Tạp chí không tồn tại!", "error")
            return redirect("/dashboard")

        # 2. Get all articles of the magazine
        articles = get_articles_by_magazine(magazine['id'])
        
        # 3. Find the target article
        target_article = None
        
        # Try finding by ID if article_slug is a digit or starts with ID-
        article_id = None
        if article_slug.isdigit():
            article_id = int(article_slug)
        elif '-' in article_slug:
            parts = article_slug.split('-', 1)
            if parts[0].isdigit():
                article_id = int(parts[0])
                
        if article_id is not None:
            # check if this article exists in the magazine
            for art in articles:
                if art['id'] == article_id:
                    target_article = art
                    break
        
        # Fallback: search by title slug
        if not target_article:
            for art in articles:
                if _slugify(art['title']) == article_slug:
                    target_article = art
                    break
                    
        if not target_article:
            flash("Bài viết không tồn tại!", "error")
            if magazine.get('slug'):
                return redirect(url_for('view_magazine_by_slug', slug=magazine['slug']))
            return redirect(url_for('view_magazine', magazine_id=magazine['id']))
            
        # Get full article details (to trigger view count increase, fetch comments and author/meta info)
        from database.article_model_simple import get_article_by_id
        article = get_article_by_id(target_article['id'])
        if not article:
            flash("Không thể tải chi tiết bài viết!", "error")
            if magazine.get('slug'):
                return redirect(url_for('view_magazine_by_slug', slug=magazine['slug']))
            return redirect(url_for('view_magazine', magazine_id=magazine['id']))

        # Deduplicate and limit sections for display
        from app.utils.helpers import _dedupe_article_content_for_display, _limit_article_sections_for_display
        article['content'] = _dedupe_article_content_for_display(article.get('content', ''))
        article['content'] = _limit_article_sections_for_display(article.get('content', ''), max_sections=5)

        # Handle comment posting (POST method)
        if request.method == "POST":
            if 'user_id' not in session:
                flash('Bạn cần đăng nhập để bình luận.', 'error')
                return redirect(url_for('login'))
            content = request.form.get('comment_content', '').strip()
            if content:
                from database.comment_model_simple import add_comment
                add_comment(article['id'], session['user_id'], content)
                return redirect(request.url)

        # Get comments
        from database.comment_model_simple import get_comments_by_article
        comments = get_comments_by_article(article['id'], user_id=session.get('user_id'))
        
        # Multi-language configuration check
        _is_en = session.get('language') == 'en' or (
            magazine.get('language') == 'en'
        )

        # Build categories menu (same as magazine_detail)
        topic_counts = get_article_topic_counts_by_magazine(magazine['id'])
        categories_menu, configured_categories = _build_categories_menu(magazine, topic_counts)

        # Build other articles for sidebar
        other_articles = [art for art in articles if art['id'] != article['id']]
        other_articles = other_articles[:6]
        _decorate_preview_articles(other_articles, configured_categories)

        return render_template(
            "magazine_article_detail.html",
            magazine=magazine,
            article=article,
            comments=comments,
            categories_menu=categories_menu,
            other_articles=other_articles,
            _is_en=_is_en,
            user_email=session.get('user_email'),
            user_role=session.get('user_role'),
        )

    # ------------------------------------------------------------------
    # Magazine settings
    # ------------------------------------------------------------------

    @app.route("/magazine/<slug>/settings", methods=["GET", "POST"])
    @login_required
    def magazine_settings(slug):
        magazine = get_magazine_by_slug(slug)
        if not magazine and slug.isdigit():
            try:
                magazine = get_magazine_by_id(int(slug))
            except Exception:
                magazine = None
        if not magazine:
            flash("Tạp chí không tồn tại!", "error")
            return redirect("/")
        if session.get('user_id') != magazine.get('user_id'):
            flash("Bạn không có quyền chỉnh sửa tạp chí này!", "error")
            if magazine.get('slug'):
                return redirect(url_for('view_magazine_by_slug', slug=magazine['slug']))
            return redirect(url_for('view_magazine', magazine_id=magazine['id']))

        action = request.form.get("_action") if request.method == "POST" else None

        if action == "archive":
            from database.magazine_model_simple import update_magazine_status
            ok = update_magazine_status(magazine['id'], session['user_id'], "archived")
            flash("Tạp chí đã được đóng (archived)." if ok else "Không thể cập nhật trạng thái tạp chí.",
                  "success" if ok else "error")
            magazine = get_magazine_by_id(magazine['id'])
            return render_template(
                "magazine_settings.html", magazine=magazine,
                user_email=session.get('user_email'), user_role=session.get('user_role'),
            )

        if action == "activate":
            from database.magazine_model_simple import update_magazine_status
            ok = update_magazine_status(magazine['id'], session['user_id'], "active")
            flash("Tạp chí đã được mở lại (active)." if ok else "Không thể cập nhật trạng thái tạp chí.",
                  "success" if ok else "error")
            magazine = get_magazine_by_id(magazine['id'])
            return render_template(
                "magazine_settings.html", magazine=magazine,
                user_email=session.get('user_email'), user_role=session.get('user_role'),
            )

        if action == "delete":
            success = delete_magazine(magazine['id'], session['user_id'])
            if success:
                flash("Đã xóa tạp chí vĩnh viễn.", "success")
                return redirect("/dashboard")
            else:
                flash("Không thể xóa tạp chí!", "error")

        if request.method == "POST" and action is None:
            title       = (request.form.get("title") or "").strip()
            description = (request.form.get("description") or "").strip()
            topic       = (request.form.get("topic") or "").strip()
            keywords    = (request.form.get("keywords") or "").strip()
            slug_input  = (request.form.get("slug") or "").strip()
            theme       = (request.form.get("theme") or "").strip() or None

            if not title:
                flash("Tiêu đề tạp chí không được để trống!", "error")
                return render_template(
                    "magazine_settings.html", magazine=magazine,
                    user_email=session.get('user_email'), user_role=session.get('user_role'),
                )

            if not slug_input:
                slug_input = _slugify(title)

            from database.magazine_model_simple import update_magazine_basic
            ok = update_magazine_basic(
                magazine_id=magazine['id'],
                title=title, slug=slug_input, topic=topic,
                description=description, keywords=keywords, theme=theme,
            )
            if not ok:
                flash("Không thể lưu cài đặt. Có thể slug đã trùng với tạp chí khác.", "error")
            else:
                if slug_input:
                    magazine = get_magazine_by_slug(slug_input) or get_magazine_by_id(magazine['id'])
                else:
                    magazine = get_magazine_by_id(magazine['id'])
                if magazine.get('slug'):
                    return redirect(url_for('magazine_settings', slug=magazine['slug']))

        return render_template(
            "magazine_settings.html", magazine=magazine,
            user_email=session.get('user_email'), user_role=session.get('user_role'),
        )

    # ------------------------------------------------------------------
    # Generate more articles
    # ------------------------------------------------------------------

    @app.route("/magazine/<int:magazine_id>/generate-more", methods=["POST"])
    @login_required
    def magazine_generate_more(magazine_id):
        magazine = get_magazine_by_id(magazine_id)
        if not magazine:
            flash("Tạp chí không tồn tại!", "error")
            return redirect("/dashboard")
        if session['user_id'] != magazine['user_id']:
            flash("Bạn không có quyền thực hiện thao tác này!", "error")
            return redirect(url_for('view_magazine', magazine_id=magazine_id))

        num               = int(request.form.get("num_articles", 2))
        selected_category = request.form.get("category_name", "").strip()
        if not selected_category:
            flash("Vui lòng chọn danh mục để tạo bài viết!", "error")
            return redirect(url_for('view_magazine', magazine_id=magazine_id))

        user_id = session['user_id']
        current_balance = get_user_token_balance(user_id)
        if current_balance < num:
            flash(
                f"Bạn cần {num} Token để tạo {num} bài viết, nhưng chỉ còn {current_balance} Token. "
                "Vui lòng mua thêm Token tại mục Gói dịch vụ.",
                "error",
            )
            return redirect(url_for('dashboard', tab='plans'))

        cat_keywords = ""
        raw_cfg = magazine.get('categories_config')
        if raw_cfg:
            try:
                parsed = json.loads(raw_cfg)
                if isinstance(parsed, list):
                    for item in parsed:
                        if not isinstance(item, dict):
                            continue
                        name = str(item.get('name', '')).strip()
                        if name and name.lower() == selected_category.lower():
                            cat_keywords = (item.get('keywords') or '').strip()
                            break
            except Exception:
                pass

        existing_articles = get_articles_by_magazine(magazine_id)
        used_source_urls = set()
        for art in existing_articles:
            if (art.get('topic') or '').strip().lower() != selected_category.lower():
                continue
            for url in art.get('source_urls') or []:
                if isinstance(url, str) and url.strip().startswith('http'):
                    used_source_urls.add(url.strip())

        try:
            article_generator._used_single_category_urls = set(used_source_urls)
        except Exception:
            pass

        base_desc = magazine.get('description') or ''
        extra     = f"; Từ khóa: {cat_keywords}" if cat_keywords else ""
        cat_description = (
            f"{base_desc} (Danh mục: {selected_category}{extra})" if base_desc
            else f"{selected_category}{extra}"
        )

        articles = []
        for _ in range(max(num, 1)):
            art = article_generator.generate_single_article_for_category(
                topic=selected_category,
                magazine_title=magazine['title'],
                description=cat_description,
                keywords=cat_keywords,
            )
            if not art:
                continue
            art['topic'] = selected_category
            articles.append(art)

        saved = 0
        for art in articles:
            aid = save_article_to_magazine(
                magazine_id=magazine_id, user_id=session['user_id'],
                title=art['title'], content=art['content'], summary=art['summary'],
                keywords=art['keywords'], topic=art['topic'],
                image_url=art.get('image_url', ''),
                image_urls=art.get('all_images') or art.get('image_urls'),
                source_urls=art.get('source_urls'),
            )
            if aid:
                saved += 1

        _refresh_magazine_category_counts(magazine_id)

        if saved > 0:
            new_balance = deduct_tokens(user_id, saved)
            if new_balance is not None:
                session['token_balance'] = new_balance

        flash(f"✅ Đã tạo thêm {saved} bài viết cho danh mục '{selected_category}'!", "success")
        return redirect(url_for('view_magazine', magazine_id=magazine_id))

    # ------------------------------------------------------------------
    # Delete magazine
    # ------------------------------------------------------------------

    @app.route("/magazine/<int:magazine_id>/delete", methods=["POST"])
    @login_required
    def delete_magazine_route(magazine_id):
        success = delete_magazine(magazine_id, session['user_id'])
        if success:
            flash("Đã xóa tạp chí!", "success")
        else:
            flash("Không thể xóa tạp chí!", "error")
        return redirect("/dashboard")

    # ------------------------------------------------------------------
    # Schedule management
    # ------------------------------------------------------------------

    @app.route("/magazine/<int:magazine_id>/schedule", methods=["GET", "POST"])
    @login_required
    def magazine_schedule(magazine_id):
        magazine = get_magazine_by_id(magazine_id)
        if not magazine:
            flash("Không tìm thấy tạp chí!", "error")
            return redirect("/dashboard")
        if magazine['user_id'] != session['user_id']:
            flash("Bạn không có quyền truy cập!", "error")
            return redirect("/dashboard")

        schedules = get_schedules_by_magazine(magazine_id)

        if request.method == "POST":
            frequency     = request.form.get("frequency", "daily")
            hour          = int(request.form.get("hour", 8))
            minute        = int(request.form.get("minute", 0))
            num_articles  = int(request.form.get("num_articles", 1) or 1)
            if num_articles < 1:
                num_articles = 1
            category_name = request.form.get("category_name", "").strip()
            keywords      = (request.form.get("keywords") or "").strip() or None
            days_of_week  = ','.join(request.form.getlist("days_of_week"))
            interval_val  = max(1, int(request.form.get("interval_val") or 5))

            if not category_name:
                flash("Vui lòng chọn danh mục cho lịch tự động!", "error")
                return redirect(url_for('magazine_schedule', magazine_id=magazine_id))

            if frequency == 'interval_min':
                interval_minutes = max(1, interval_val)
            elif frequency == 'interval_hour':
                interval_minutes = max(1, interval_val) * 60
            else:
                interval_minutes = 0

            schedule_id = create_schedule(
                magazine_id=magazine_id, user_id=session['user_id'],
                frequency=frequency, hour=hour, minute=minute,
                num_articles=num_articles, category_name=category_name,
                days_of_week=days_of_week, interval_minutes=interval_minutes,
                keywords=keywords,
            )
            if schedule_id:
                new_sched = get_schedule_by_id(schedule_id)
                if new_sched:
                    new_sched['magazine_title'] = magazine['title']
                    new_sched['topic']          = new_sched.get('category_name') or magazine['topic']
                    new_sched['keywords']       = new_sched.get('keywords') or magazine['keywords']
                    new_sched['description']    = magazine.get('description', '')
                    _register_schedule_job(new_sched)
                flash("✅ Đã tạo lịch tự động sinh bài viết!", "success")
            else:
                flash("❌ Không thể tạo lịch, vui lòng thử lại!", "error")
            # Nếu gọi từ tab schedules trên dashboard thì redirect về đó
            if request.form.get('_ret_tab') == 'schedules':
                return redirect(url_for('dashboard', tab='schedules'))
            return redirect(url_for('magazine_schedule', magazine_id=magazine_id))

        return render_template(
            "magazine_schedule.html",
            magazine=magazine, schedules=schedules,
            categories_menu=(
                magazine.get('categories_config') and
                fromjson_filter(magazine.get('categories_config'))
            ) or [],
            user_email=session.get('user_email'),
            user_role=session.get('user_role'),
        )

    @app.route("/schedule/<int:schedule_id>/toggle", methods=["POST"])
    @login_required
    def toggle_schedule_route(schedule_id):
        from app.extensions import scheduler
        schedule = get_schedule_by_id(schedule_id)
        if not schedule or schedule['user_id'] != session['user_id']:
            flash("Không có quyền thực hiện!", "error")
            return redirect("/dashboard")
        toggle_schedule(schedule_id, session['user_id'])
        updated = get_schedule_by_id(schedule_id)
        if updated['is_active']:
            mag = get_magazine_by_id(updated['magazine_id'])
            updated['magazine_title'] = mag['title']
            updated['topic']          = updated.get('category_name') or mag['topic']
            updated['keywords']       = mag['keywords']
            updated['description']    = mag.get('description', '')
            _register_schedule_job(updated)
        else:
            job_id = f"sched_{schedule_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
        # Nếu đến từ tab schedules trên dashboard thì redirect về đó
        ref = request.referrer or ''
        if 'tab=schedules' in ref:
            return redirect(url_for('dashboard', tab='schedules'))
        return redirect(url_for('magazine_schedule', magazine_id=schedule['magazine_id']))

    @app.route("/schedule/<int:schedule_id>/delete", methods=["POST"])
    @login_required
    def delete_schedule_route(schedule_id):
        from app.extensions import scheduler
        schedule = get_schedule_by_id(schedule_id)
        if not schedule or schedule['user_id'] != session['user_id']:
            flash("Không có quyền thực hiện!", "error")
            return redirect("/dashboard")
        mag_id = schedule['magazine_id']
        job_id = f"sched_{schedule_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        delete_schedule(schedule_id, session['user_id'])
        # Nếu request đến từ dashboard tab schedules thì redirect về đó
        ref = request.referrer or ''
        if 'tab=schedules' in ref or ref.endswith('/dashboard'):
            return redirect(url_for('dashboard', tab='schedules',
                                    mag_id=request.args.get('mag_id')))
        return redirect(url_for('magazine_schedule', magazine_id=mag_id))

    @app.route("/schedule/<int:schedule_id>/edit", methods=["POST"])
    @login_required
    def edit_schedule_route(schedule_id):
        from app.extensions import scheduler
        from database.schedule_model_simple import update_schedule
        schedule = get_schedule_by_id(schedule_id)
        if not schedule or schedule['user_id'] != session['user_id']:
            flash("Không có quyền thực hiện!", "error")
            return redirect("/dashboard")

        category_name = (request.form.get("category_name") or "").strip()
        keywords      = (request.form.get("keywords") or "").strip() or None
        frequency     = request.form.get("frequency", "daily")
        hour          = int(request.form.get("hour") or 8)
        minute        = int(request.form.get("minute") or 0)
        num_articles  = max(1, int(request.form.get("num_articles") or 1))
        days_of_week  = ','.join(request.form.getlist("days_of_week"))
        interval_val  = max(1, int(request.form.get("interval_val") or 5))

        if not category_name:
            flash("Vui lòng nhập tên danh mục!", "error")
        else:
            if frequency == 'interval_min':
                interval_minutes = interval_val
            elif frequency == 'interval_hour':
                interval_minutes = interval_val * 60
            else:
                interval_minutes = 0

            ok = update_schedule(
                schedule_id=schedule_id, user_id=session['user_id'],
                category_name=category_name, keywords=keywords,
                frequency=frequency, hour=hour, minute=minute,
                num_articles=num_articles, days_of_week=days_of_week,
                interval_minutes=interval_minutes,
            )
            if ok:
                # Re-register job with new settings
                updated = get_schedule_by_id(schedule_id)
                if updated and updated['is_active']:
                    mag = get_magazine_by_id(updated['magazine_id'])
                    if mag:
                        updated['magazine_title'] = mag['title']
                        updated['topic']          = updated.get('category_name') or mag['topic']
                        updated['keywords']       = updated.get('keywords') or mag['keywords']
                        updated['description']    = mag.get('description', '')
                        _register_schedule_job(updated)
            else:
                flash("❌ Không thể cập nhật lịch!", "error")

        ref = request.referrer or ''
        if 'tab=schedules' in ref:
            return redirect(url_for('dashboard', tab='schedules',
                                    mag_id=request.form.get('mag_id')))
        return redirect(url_for('magazine_schedule', magazine_id=schedule['magazine_id']))
