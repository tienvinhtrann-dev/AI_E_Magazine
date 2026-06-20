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

    # ── Job store đơn giản (in-memory, đủ cho 1 server process) ──────────────
    import threading, uuid as _uuid, time as _time
    _gen_jobs: dict = {}   # job_id → {status, created, total, error, mag_id, user_id}
    _gen_jobs_lock = threading.Lock()

    def _bg_generate(app_ctx, job_id, user_id, mag_id, magazine,
                     names, counts_raw, keywords_list,
                     desc_base, kw_base):
        """Background thread: tạo bài theo từng danh mục rồi cập nhật job store."""
        with app_ctx:
            # Reset cache crawl của generator trước khi bắt đầu phiên mới
            try:
                article_generator.clear_crawled_cache()
            except Exception:
                pass

            last_job_err = None

            MAX_TOTAL = 8
            total_requested = 0
            created_count   = 0
            global_used_source_urls = set()


            # Thu thập URL nguồn đã dùng
            try:
                existing_articles = get_articles_by_magazine(mag_id)
                for art in existing_articles:
                    for url in art.get("source_urls") or []:
                        if isinstance(url, str) and url.strip().startswith("http"):
                            global_used_source_urls.add(url.strip())
            except Exception:
                pass

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

                kw_specific = (keywords_list[idx] or "").strip() if idx < len(keywords_list) else ""
                cat_keywords = kw_specific or kw_base or name
                extra = f"; Từ khóa: {cat_keywords}" if cat_keywords else ""
                cat_description = (
                    f"{desc_base} (Danh mục: {name}{extra})" if desc_base
                    else f"{name}{extra}"
                )

                for _ in range(count):
                    if total_requested >= MAX_TOTAL:
                        break
                    total_requested += 1

                    try:
                        art = article_generator.generate_single_article_for_category(
                            topic=name,
                            magazine_title=magazine["title"],
                            description=cat_description,
                            keywords=cat_keywords,
                        )
                    except Exception as e_art:
                        print(f"[BG-WARN] generate error (category='{name}'): {e_art}")
                        art = None

                    if not art:
                        err_msg = getattr(article_generator, 'last_error', None)
                        if err_msg:
                            last_job_err = err_msg
                        continue

                    for url in art.get("source_urls") or []:
                        if isinstance(url, str) and url.strip().startswith("http"):
                            global_used_source_urls.add(url.strip())
                    try:
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
                            # Cập nhật job store sau mỗi bài tạo xong
                            with _gen_jobs_lock:
                                _gen_jobs[job_id]["created"] = created_count
                    except Exception as e_save:
                        print(f"[BG-WARN] save error: {e_save}")

                if total_requested >= MAX_TOTAL:
                    break

            # Trừ token sau khi hoàn thành
            if created_count > 0:
                try:
                    deduct_tokens(user_id, created_count)
                    _refresh_magazine_category_counts(mag_id)
                except Exception:
                    pass

            with _gen_jobs_lock:
                if created_count == 0:
                    _gen_jobs[job_id]["status"] = "failed"
                    _gen_jobs[job_id]["error"] = last_job_err or "Không tìm thấy bài viết phù hợp với từ khóa/danh mục đã nhập. Vui lòng thử lại với từ khóa khác hoặc đổi danh mục."
                else:
                    _gen_jobs[job_id]["status"] = "done"
                _gen_jobs[job_id]["created"] = created_count

            print(f"[BG] Job {job_id} done: {created_count}/{total_requested} articles created.")

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

        # Tính tổng bài cần tạo để kiểm tra token
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

        if total_needed == 0:
            if is_ajax: return jsonify({"ok": False, "error": "Bạn chưa chọn số bài cho bất kỳ danh mục nào."})
            flash("Bạn chưa chọn số bài cho bất kỳ danh mục nào.", "warning")
            return redirect(url_for("dashboard", tab="posts", mag_id=mag_id))

        current_balance = get_user_token_balance(user_id)
        if current_balance < total_needed:
            err_msg = (f"Bạn cần {total_needed} Token để tạo {total_needed} bài viết, "
                       f"nhưng chỉ còn {current_balance} Token. "
                       "Vui lòng mua thêm Token tại mục Gói dịch vụ.")
            if is_ajax: return jsonify({"ok": False, "error": err_msg, "redirect_tab": "plans"})
            flash(err_msg, "error")
            return redirect(url_for("dashboard", tab="plans"))

        desc_base = (magazine.get("description") or "").strip()
        kw_base   = (magazine.get("keywords") or "").strip()

        # Tạo job ID và khởi động background thread
        job_id = str(_uuid.uuid4())[:12]
        with _gen_jobs_lock:
            _gen_jobs[job_id] = {
                "status": "running",
                "created": 0,
                "total": total_needed,
                "mag_id": mag_id,
                "user_id": user_id,
                "started": _time.time(),
            }

        # Push application context vào thread
        app_ctx = app.app_context()
        t = threading.Thread(
            target=_bg_generate,
            args=(app_ctx, job_id, user_id, mag_id, magazine,
                  list(names), list(counts_raw), list(keywords_list),
                  desc_base, kw_base),
            daemon=True,
        )
        t.start()

        if is_ajax:
            return jsonify({"ok": True, "job_id": job_id, "total": total_needed,
                            "message": f"Đang tạo {total_needed} bài viết trong nền..."})

        flash(f"✅ Đang tạo {total_needed} bài viết trong nền. Trang sẽ tự động cập nhật sau vài phút.", "success")
        return redirect(url_for("dashboard", tab="posts", mag_id=mag_id))

    @app.route("/dashboard/posts/generate-status/<job_id>")
    @login_required
    def dashboard_generate_status(job_id):
        """Polling endpoint: trả về trạng thái job tạo bài."""
        with _gen_jobs_lock:
            job = _gen_jobs.get(job_id)
        if not job:
            return jsonify({"ok": False, "error": "Job not found"}), 404
        if job.get("user_id") != session.get("user_id"):
            return jsonify({"ok": False, "error": "Forbidden"}), 403
        return jsonify({
            "ok": True,
            "status": job.get("status"),
            "created": job.get("created", 0),
            "total": job.get("total", 0),
            "error": job.get("error", "")
        })


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

        # Reset cache crawl của generator trước khi bắt đầu phiên mới
        try:
            article_generator.clear_crawled_cache()
        except Exception:
            pass

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
