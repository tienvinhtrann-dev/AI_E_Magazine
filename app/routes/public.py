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
