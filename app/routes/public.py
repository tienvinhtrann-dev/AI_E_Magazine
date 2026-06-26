"""
Public routes: homepage, article detail, search, comment API.
"""
import json as _json
from flask import session, flash, redirect, url_for, render_template, request, jsonify, make_response

from app.utils.decorators import login_required
from app.utils.helpers import (
    _dedupe_article_content_for_display,
    _limit_article_sections_for_display,
)
from database.article_model_simple import (
    get_article_by_id, get_articles, get_top_view_articles, search_articles,
    get_related_articles,
)
from database.comment_model_simple import (
    get_comments_by_article, add_comment, like_comment, reply_comment,
)
from database.magazine_model_simple import get_all_magazines
from database.user_model_simple import is_admin
from database.feedback_model import create_feedback


def register_routes(app):

    @app.route("/")
    def home():
        magazines  = get_all_magazines(limit=50)
        user_email = session.get('user_email')
        user_role  = session.get('user_role')
        resp = make_response(render_template(
            "home.html",
            magazines=magazines,
            user_email=user_email,
            user_role=user_role,
        ))
        # Cache 10 giây ở browser/proxy — giúp click từ dashboard hiện liền
        resp.headers['Cache-Control'] = 'private, max-age=10'
        return resp

    @app.route("/privacy-policy")
    def privacy_policy():
        return render_template("privacy_policy.html")

    @app.route("/terms-of-service")
    def terms_of_service():
        return render_template("terms_of_service.html")

    @app.route("/data-deletion")
    def data_deletion():
        return render_template("data_deletion.html")

    @app.route("/support")
    def support_page():
        return render_template("support.html")

    @app.route('/contact-feedback', methods=['POST'])
    def contact_feedback_submit():
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip()
        subject = (request.form.get('subject') or '').strip()
        message = (request.form.get('message') or '').strip()

        if not name or not email or not message:
            flash('Vui lòng nhập đầy đủ họ tên, email và nội dung phản hồi.', 'error')
            return redirect('/#lien-he')

        saved = create_feedback(
            name=name,
            email=email,
            subject=subject,
            message=message,
            source_page='home',
            ip_address=(request.headers.get('X-Forwarded-For') or request.remote_addr or '')[:45],
            user_agent=(request.headers.get('User-Agent') or '')[:255],
        )
        if saved:
            flash('Đã gửi phản hồi thành công. Cảm ơn bạn đã liên hệ!', 'success')
        else:
            flash('Không thể gửi phản hồi lúc này. Vui lòng thử lại sau.', 'error')
        return redirect('/#lien-he')

    @app.route("/api/data-deletion-request", methods=["POST"])
    def api_data_deletion_request():
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip()
        reason = (data.get('reason') or '').strip()
        notes = (data.get('notes') or '').strip()
        
        if not email:
            return jsonify({'success': False, 'error': 'Vui lòng cung cấp Gmail đăng ký'}), 400
            
        message = f"Lý do xóa tài khoản: {reason}\nGhi chú thêm: {notes}"
        
        saved = create_feedback(
            name="Yêu cầu xóa tài khoản",
            email=email,
            subject="Yêu cầu xóa tài khoản & dữ liệu",
            message=message,
            source_page='data_deletion',
            ip_address=(request.headers.get('X-Forwarded-For') or request.remote_addr or '')[:45],
            user_agent=(request.headers.get('User-Agent') or '')[:255],
        )
        if saved:
            return jsonify({'success': True, 'message': 'Gửi yêu cầu xóa tài khoản thành công'})
        else:
            return jsonify({'success': False, 'error': 'Lỗi lưu dữ liệu yêu cầu'})

    @app.route("/article/<int:article_id>", methods=["GET", "POST"])
    def article_detail(article_id):
        article = get_article_by_id(article_id)
        if not article:
            flash('Bài viết không tồn tại', 'error')
            return redirect('/')
        article['content'] = _dedupe_article_content_for_display(article.get('content', ''))
        article['content'] = _limit_article_sections_for_display(article.get('content', ''), max_sections=5)
        if article['status'] != 'published':
            if 'user_id' not in session or (
                session['user_id'] != article['user_id'] and
                not is_admin(session['user_id'])
            ):
                flash('Bạn không có quyền xem bài viết này', 'error')
                return redirect('/')
        if request.method == "POST":
            if 'user_id' not in session:
                flash('Bạn cần đăng nhập để bình luận.', 'error')
                return redirect(url_for('login'))
            content = request.form.get('comment_content', '').strip()
            if content:
                add_comment(article_id, session['user_id'], content)
                return redirect(request.url)
        comments = get_comments_by_article(article_id, user_id=session.get('user_id'))
        related_articles = []
        if article.get('topic'):
            related_articles = get_related_articles(
                topic=article['topic'],
                exclude_id=article_id,
                limit=4,
            )
        top_articles = get_top_view_articles(6)
        return render_template(
            "article_detail.html",
            article=article,
            related_articles=related_articles,
            top_articles=top_articles,
            comments=comments,
            user_email=session.get('user_email'),
            user_role=session.get('user_role'),
        )

    @app.route("/api/article/<int:article_id>")
    def api_article_detail(article_id):
        article = get_article_by_id(article_id)
        if not article:
            return jsonify({'error': 'Không tìm thấy bài viết'}), 404
        if article['status'] != 'published':
            if 'user_id' not in session or (
                session['user_id'] != article['user_id'] and
                not is_admin(session['user_id'])
            ):
                return jsonify({'error': 'Không có quyền xem bài viết này'}), 403
        article['content'] = _dedupe_article_content_for_display(article.get('content', ''))
        article['content'] = _limit_article_sections_for_display(article.get('content', ''), max_sections=5)
        img_urls = []
        raw_imgs = article.get('image_urls')
        if raw_imgs:
            if isinstance(raw_imgs, list):
                img_urls = raw_imgs
            elif isinstance(raw_imgs, str):
                if raw_imgs.startswith('http'):
                    img_urls = [raw_imgs]
                else:
                    try:
                        img_urls = _json.loads(raw_imgs.replace("'", '"'))
                    except Exception:
                        img_urls = []
        source_urls = []
        raw_src = article.get('source_urls')
        if raw_src:
            if isinstance(raw_src, list):
                source_urls = raw_src
            elif isinstance(raw_src, str):
                try:
                    source_urls = _json.loads(raw_src.replace("'", '"'))
                except Exception:
                    source_urls = [raw_src] if raw_src.startswith('http') else []
        # Skip loading comments khi caller không cần (popup dashboard)
        comments_data = []
        if not request.args.get('no_comments'):
            comments = get_comments_by_article(article_id, user_id=session.get('user_id'))
            for c in comments:
                comments_data.append({
                    'id':         c.get('id'),
                    'user_name':  c.get('user_name') or c.get('user_email', ''),
                    'content':    c.get('content', ''),
                    'created_at': (
                        c.get('created_at').strftime('%d/%m/%Y %H:%M')
                        if hasattr(c.get('created_at'), 'strftime')
                        else str(c.get('created_at', ''))
                    ),
                })
        created_str = ''
        if article.get('created_at'):
            ca = article['created_at']
            created_str = ca.strftime('%d/%m/%Y %H:%M') if hasattr(ca, 'strftime') else str(ca)
        is_owner = (
            session.get('user_id') == article.get('user_id') or
            session.get('user_role') == 'admin'
        )
        return jsonify({
            'id':          article['id'],
            'title':       article.get('title', ''),
            'summary':     article.get('summary', ''),
            'content':     article.get('content', ''),
            'keywords':    article.get('keywords', ''),
            'topic':       article.get('topic', ''),
            'author_name': article.get('author_name') or article.get('author_email', 'AI Writer'),
            'created_at':  created_str,
            'view_count':  article.get('view_count', 0),
            'status':      article.get('status', ''),
            'image_urls':  img_urls,
            'source_urls': source_urls,
            'comments':    comments_data,
            'is_owner':    is_owner,
        })

    @app.route("/search")
    def search():
        keyword = request.args.get('q', '')
        if not keyword:
            return redirect('/')
        articles = search_articles(keyword)
        return render_template(
            "search_results.html",
            keyword=keyword,
            articles=articles,
            user_email=session.get('user_email'),
        )

    # ------------------------------------------------------------------
    # Comment API
    # ------------------------------------------------------------------

    @app.route("/api/article/<int:article_id>/comments")
    def api_article_comments(article_id):
        """Lightweight endpoint - chỉ trả về comments, không load toàn bộ article."""
        comments = get_comments_by_article(article_id, user_id=session.get('user_id'))
        comments_data = []
        for c in comments:
            comments_data.append({
                'id':         c.get('id'),
                'user_name':  c.get('user_name') or c.get('user_email', ''),
                'content':    c.get('content', ''),
                'created_at': (
                    c.get('created_at').strftime('%d/%m/%Y %H:%M')
                    if hasattr(c.get('created_at'), 'strftime')
                    else str(c.get('created_at', ''))
                ),
            })
        return jsonify({'comments': comments_data, 'count': len(comments_data)})

    @app.route("/api/comment/<int:comment_id>/like", methods=["POST"])
    @login_required
    def api_like_comment(comment_id):
        result = like_comment(comment_id, session['user_id'])
        if result:
            return jsonify(result)
        return jsonify({'success': False, 'error': 'Không thể thích bình luận'}), 400

    @app.route("/api/comment/<int:comment_id>/reply", methods=["POST"])
    @login_required
    def api_reply_comment(comment_id):
        content    = request.json.get('content', '').strip()
        article_id = request.json.get('article_id')
        if not content or not article_id:
            return jsonify({'success': False, 'error': 'Nội dung trả lời không hợp lệ'}), 400
        reply_id = reply_comment(article_id, comment_id, session['user_id'], content)
        if reply_id:
            return jsonify({'success': True, 'reply_id': reply_id})
        return jsonify({'success': False, 'error': 'Không thể trả lời bình luận'}), 400

    @app.route("/import-db-magic-xyz")
    def import_db_magic():
        import os
        from database.db_simple import get_connection

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sql_file_path = os.path.join(project_root, 'database.sql')
        if not os.path.exists(sql_file_path):
            return f"Error: database.sql not found at {sql_file_path}"

        conn = get_connection()
        if not conn:
            return "Error: Could not connect to the database."

        try:
            cursor = conn.cursor()
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # Split SQL file by statements, accounting for quotes
            statements = []
            current_statement = []
            in_string = False
            string_char = None
            escaped = False

            for char in sql_content:
                current_statement.append(char)
                if escaped:
                    escaped = False
                    continue
                if char == '\\':
                    escaped = True
                    continue
                if char in ("'", '"') and not escaped:
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif string_char == char:
                        in_string = False
                        string_char = None
                elif char == ';' and not in_string:
                    statements.append("".join(current_statement).strip())
                    current_statement = []

            if current_statement:
                stmt_str = "".join(current_statement).strip()
                if stmt_str:
                    statements.append(stmt_str)

            executed_count = 0
            error_count = 0
            errors = []
            for stmt in statements:
                stmt_clean = stmt.strip()
                if not stmt_clean:
                    continue
                # Skip comments unless they are MySQL executable comments (starts with /*!)
                if stmt_clean.startswith('--') or stmt_clean.startswith('#'):
                    continue
                if stmt_clean.startswith('/*') and not stmt_clean.startswith('/*!'):
                    continue
                try:
                    cursor.execute(stmt_clean)
                    executed_count += 1
                except Exception as ex:
                    error_count += 1
                    errors.append(f"Stmt: {stmt_clean[:100]}... | Error: {ex}")

            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()
            cursor.close()
            conn.close()

            res = f"Import success!<br>Executed: {executed_count} statements.<br>Errors: {error_count}.<br>"
            if errors:
                res += "<br>Detailed errors:<br>" + "<br>".join(errors)
            return res
        except Exception as e:
            if conn:
                try:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                except:
                    pass
                conn.close()
            return f"Fatal Error: {e}"

