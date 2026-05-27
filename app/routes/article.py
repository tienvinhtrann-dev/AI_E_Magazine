"""
Article routes: create, generate (AI), edit, publish, delete.
Also: dashboard quick-generate by category.
"""
import json
import os
import time
from flask import session, flash, redirect, url_for, render_template, request, jsonify
from werkzeug.utils import secure_filename

from app.utils.decorators import login_required
from app.utils.helpers import _refresh_magazine_category_counts
from app.extensions import article_generator
from database.article_model_simple import (
    create_article, get_article_by_id, update_article,
    delete_article, publish_article,
)
from database.magazine_model_simple import (
    get_magazine_by_id, get_articles_by_magazine, save_article_to_magazine,
)
from database.user_model_simple import (
    is_admin, get_user_token_balance, deduct_tokens,
)


def register_routes(app):

    @app.route("/create", methods=["GET", "POST"])
    @login_required
    def create_article_page():
        if request.method == "POST":
            topic       = request.form.get("topic")
            description = request.form.get("description")
            keywords    = request.form.get("keywords")
            if not topic or not keywords:
                flash("Vui lòng điền đầy đủ chủ đề và từ khóa", "error")
                return render_template("create_article.html")
            return redirect(url_for('generate_article',
                                    topic=topic, description=description, keywords=keywords))
        return render_template(
            "create_article.html",
            user_email=session['user_email'],
            user_role=session.get('user_role'),
        )

    @app.route("/dashboard/posts/generate-by-category", methods=["POST"])
    @login_required
    def dashboard_generate_by_category():
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        user_id = session.get("user_id")
        mag_id  = request.form.get("magazine_id", type=int)

        if not mag_id:
            if is_ajax: return jsonify({"ok": False, "error": "Không xác định được tạp chí để tạo bài."})
            flash("Không xác định được tạp chí để tạo bài.", "error")
            return redirect(url_for("dashboard", tab="posts"))

        magazine = get_magazine_by_id(mag_id)
        if not magazine:
            if is_ajax: return jsonify({"ok": False, "error": "Tạp chí không tồn tại."})
            flash("Tạp chí không tồn tại.", "error")
            return redirect(url_for("dashboard", tab="posts"))
        if magazine.get("user_id") != user_id:
            if is_ajax: return jsonify({"ok": False, "error": "Bạn không có quyền tạo bài cho tạp chí này."})
            flash("Bạn không có quyền tạo bài cho tạp chí này.", "error")
            return redirect(url_for("dashboard", tab="posts", mag_id=mag_id))

        names         = request.form.getlist("category_name")
        counts_raw    = request.form.getlist("category_count")
        keywords_list = request.form.getlist("category_keywords")

        total_needed = 0
        for idx, name in enumerate(names):
            if not (name or "").strip():
                continue
            try:
                cnt = int(counts_raw[idx]) if idx < len(counts_raw) else 0
            except Exception:
                cnt = 0
            if cnt > 0:
                total_needed += cnt
        total_needed = min(total_needed, 8)

        if total_needed > 0:
            current_balance = get_user_token_balance(user_id)
            if current_balance < total_needed:
                err_msg = (f"Bạn cần {total_needed} Token để tạo {total_needed} bài viết, "
                           f"nhưng chỉ còn {current_balance} Token. "
                           "Vui lòng mua thêm Token tại mục Gói dịch vụ.")
                if is_ajax: return jsonify({"ok": False, "error": err_msg, "redirect_tab": "plans"})
                flash(err_msg, "error")
                return redirect(url_for("dashboard", tab="plans"))

        total_requested = 0
        created_count   = 0
        error_any       = False
        desc_base       = (magazine.get("description") or "").strip()
        kw_base         = (magazine.get("keywords") or "").strip()
        MAX_TOTAL       = 8

        existing_articles = get_articles_by_magazine(mag_id)
        global_used_source_urls = set()
        for art in existing_articles:
            for url in art.get("source_urls") or []:
                if isinstance(url, str) and url.strip().startswith("http"):
                    global_used_source_urls.add(url.strip())

        try:
            for idx, name in enumerate(names):
                name = (name or "").strip()
                if not name:
                    continue
                try:
                    count = int(counts_raw[idx]) if idx < len(counts_raw) else 0
                except Exception:
                    count = 0
                if count <= 0:
                    continue

                try:
                    article_generator._used_single_category_urls = set(global_used_source_urls)
                except Exception:
                    pass

                kw_specific = ""
                if idx < len(keywords_list):
                    kw_specific = (keywords_list[idx] or "").strip()
                cat_keywords = kw_specific or kw_base or name

                base_desc = desc_base or ""
                extra     = f"; Từ khóa: {cat_keywords}" if cat_keywords else ""
                cat_description = (
                    f"{base_desc} (Danh mục: {name}{extra})" if base_desc
                    else f"{name}{extra}"
                )

                for _ in range(count):
                    if total_requested >= MAX_TOTAL:
                        break
                    total_requested += 1
                    art = article_generator.generate_single_article_for_category(
                        topic=name,
                        magazine_title=magazine["title"],
                        description=cat_description,
                        keywords=cat_keywords,
                    )
                    if not art:
                        error_any = True
                        continue
                    for url in art.get("source_urls") or []:
                        if isinstance(url, str) and url.strip().startswith("http"):
                            global_used_source_urls.add(url.strip())
                    aid = save_article_to_magazine(
                        magazine_id=mag_id, user_id=user_id,
                        title=art.get("title"), content=art.get("content"),
                        summary=art.get("summary"), keywords=art.get("keywords"),
                        topic=art.get("topic"), image_url=art.get("image_url", ""),
                        image_urls=art.get("all_images") or art.get("image_urls"),
                        source_urls=art.get("source_urls"),
                    )
                    if aid:
                        created_count += 1
                if total_requested >= MAX_TOTAL:
                    break
        except Exception as e:
            print(f"[ERR] dashboard_generate_by_category: {e}")
            error_any = True

        try:
            _refresh_magazine_category_counts(mag_id)
        except Exception:
            pass

        new_balance = None
        if created_count == 0:
            msg = "Không tạo được bài viết nào từ danh mục. Vui lòng thử lại." if error_any else "Bạn chưa chọn số bài cho bất kỳ danh mục nào."
            if is_ajax: return jsonify({"ok": False, "created": 0, "error": msg})
            flash(msg, "error" if error_any else "warning")
        else:
            new_balance = deduct_tokens(user_id, created_count)
            if new_balance is not None:
                session['token_balance'] = new_balance
                session.modified = True
            if is_ajax:
                return jsonify({"ok": True, "created": created_count, "new_balance": new_balance})

        return redirect(url_for("dashboard", tab="posts", mag_id=mag_id))

    @app.route("/generate")
    @login_required
    def generate_article():
        topic       = request.args.get('topic')
        description = request.args.get('description', '')
        keywords    = request.args.get('keywords')
        return render_template(
            "generate_progress.html",
            topic=topic, description=description, keywords=keywords,
            user_email=session['user_email'],
        )

    @app.route("/api/generate", methods=["POST"])
    @login_required
    def api_generate_article():
        data     = request.get_json()
        topic    = data.get('topic')
        description = data.get('description', '')
        keywords = data.get('keywords')
        if not topic or not keywords:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        user_id = session['user_id']
        current_balance = get_user_token_balance(user_id)
        if current_balance < 1:
            return jsonify({
                'success': False,
                'error': 'Bạn không còn Token. Vui lòng mua thêm Token tại mục Gói dịch vụ.',
                'redirect_url': url_for('dashboard', tab='plans'),
            }), 403

        result = article_generator.generate_article(
            user_id=user_id, topic=topic, description=description,
            keywords=keywords, max_sources=5,
        )
        if not result['success']:
            return jsonify(result), 400

        article_data = result['article']
        article_id = create_article(
            user_id=user_id,
            title=article_data['title'], content=article_data['content'],
            summary=article_data['summary'], keywords=article_data['keywords'],
            topic=article_data['topic'], description=article_data['description'],
            status='draft',
            source_urls=article_data.get('source_urls', []),
            image_urls=article_data.get('image_urls', []),
        )
        if article_id:
            new_balance = deduct_tokens(user_id, 1)
            if new_balance is not None:
                session['token_balance'] = new_balance
            return jsonify({
                'success': True,
                'article_id': article_id,
                'redirect_url': url_for('edit_article', article_id=article_id),
            })
        return jsonify({'success': False, 'error': 'Failed to save article'}), 500

    @app.route("/edit/<int:article_id>", methods=["GET", "POST"])
    @login_required
    def edit_article(article_id):
        article = get_article_by_id(article_id)
        if not article:
            flash('Bài viết không tồn tại', 'error')
            return redirect('/dashboard')
        if article['user_id'] != session['user_id'] and not is_admin(session['user_id']):
            flash('Bạn không có quyền chỉnh sửa bài viết này', 'error')
            return redirect('/dashboard')
        _ALLOWED_IMG_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

        if request.method == "POST":
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            try:
                title    = request.form.get("title")
                content  = request.form.get("content")
                summary  = request.form.get("summary")
                keywords = request.form.get("keywords")

                update_kwargs = dict(title=title, content=content, summary=summary, keywords=keywords)

                # Handle image action
                image_action = request.form.get('image_action', 'keep')
                if image_action == 'url':
                    new_url = (request.form.get('image_url_new') or '').strip()
                    if new_url.startswith('http'):
                        update_kwargs['image_urls'] = [new_url]
                elif image_action == 'upload':
                    f = request.files.get('image_upload')
                    if f and f.filename:
                        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
                        if ext in _ALLOWED_IMG_EXT:
                            upload_dir = os.path.join(app.static_folder, 'images', 'uploads')
                            os.makedirs(upload_dir, exist_ok=True)
                            fname = secure_filename(f.filename)
                            unique_fname = f"{int(time.time())}_{fname}"
                            f.save(os.path.join(upload_dir, unique_fname))
                            update_kwargs['image_urls'] = [url_for('static', filename=f'images/uploads/{unique_fname}')]

                success = update_article(article_id=article_id, user_id=session['user_id'], **update_kwargs)
                if is_ajax:
                    img_url = (update_kwargs.get('image_urls') or [''])[0]
                    return jsonify({'success': bool(success), 'title': title or '', 'image_url': img_url})
                if success:
                    flash('Cập nhật bài viết thành công', 'success')
                    return redirect(url_for('edit_article', article_id=article_id))
                else:
                    flash('Cập nhật thất bại', 'error')
            except Exception as _e:
                print(f'❌ edit_article error: {_e}')
                if is_ajax:
                    return jsonify({'success': False, 'error': str(_e)}), 500
                flash('Cập nhật thất bại', 'error')
        return render_template(
            "edit_article.html", article=article,
            user_email=session['user_email'],
        )

    @app.route("/publish/<int:article_id>", methods=["POST"])
    @login_required
    def publish_article_route(article_id):
        article = get_article_by_id(article_id)
        if not article:
            flash('Bài viết không tồn tại', 'error')
            return redirect('/dashboard')
        if article['user_id'] != session['user_id'] and not is_admin(session['user_id']):
            flash('Bạn không có quyền xuất bản bài viết này', 'error')
            return redirect('/dashboard')
        success = publish_article(article_id, session['user_id'])
        if success:
            if is_admin(session['user_id']):
                flash('Bài viết đã được xuất bản', 'success')
            else:
                flash('Bài viết đã được gửi chờ duyệt. Admin sẽ xem xét và phê duyệt.', 'info')
        else:
            flash('Xuất bản thất bại', 'error')
        return redirect(url_for('article_detail', article_id=article_id))

    @app.route("/delete/<int:article_id>", methods=["POST"])
    @login_required
    def delete_article_route(article_id):
        article = get_article_by_id(article_id)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if not article:
            if is_ajax:
                return jsonify({'success': False, 'error': 'Bài viết không tồn tại'}), 404
            return redirect('/dashboard')
        if article['user_id'] != session['user_id'] and not is_admin(session['user_id']):
            if is_ajax:
                return jsonify({'success': False, 'error': 'Không có quyền'}), 403
            return redirect('/dashboard')
        success = delete_article(article_id)
        if is_ajax:
            return jsonify({'success': bool(success)})
        return redirect('/dashboard')
