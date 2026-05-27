"""
Article Model - Simplified Version
Quản lý bài báo
"""
from database.db_simple import get_connection
import json
from datetime import datetime


# ----------------------------------
# Tạo Article Mới
# ----------------------------------
def create_article(user_id, title, content, **kwargs):
    """
    Tạo bài báo mới
    
    Args:
        user_id: ID người tạo
        title: Tiêu đề bài báo
        content: Nội dung bài báo
        **kwargs: summary, keywords, topic, description, status, source_urls
    
    Returns:
        article_id nếu thành công, None nếu thất bại
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        
        # Lấy các giá trị optional
        summary = kwargs.get('summary', '')
        keywords = kwargs.get('keywords', '')
        topic = kwargs.get('topic', '')
        description = kwargs.get('description', '')
        status = kwargs.get('status', 'draft')
        source_urls = kwargs.get('source_urls', [])
        image_urls = kwargs.get('image_urls', [])
        
        # Convert to JSON string
        if isinstance(source_urls, list):
            source_urls = json.dumps(source_urls)
        if isinstance(image_urls, list):
            image_urls = json.dumps(image_urls)
        
        query = """
        INSERT INTO articles 
        (user_id, title, content, summary, keywords, topic, description, status, source_urls, image_urls) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            user_id, title, content, summary, keywords, 
            topic, description, status, source_urls, image_urls
        ))
        conn.commit()
        
        article_id = cursor.lastrowid
        
        cursor.close()
        conn.close()
        
        print(f"✅ Article created: ID={article_id}, Title={title[:50]}...")
        return article_id
        
    except Exception as e:
        print(f"❌ Error creating article: {e}")
        if conn:
            conn.close()
        return None


# ----------------------------------
# Lấy Article theo ID
# ----------------------------------
def get_article_by_id(article_id):
    """Lấy chi tiết một bài báo"""
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT a.*, u.email as author_email, u.full_name as author_name
        FROM articles a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.id = %s
        """
        cursor.execute(query, (article_id,))
        article = cursor.fetchone()
        
        if article and isinstance(article, dict):
            # Parse source_urls và image_urls từ JSON
            if article.get('source_urls'):
                try:
                    article['source_urls'] = json.loads(article['source_urls'])
                except (json.JSONDecodeError, TypeError):
                    article['source_urls'] = []
            else:
                article['source_urls'] = []
                
            if article.get('image_urls'):
                try:
                    article['image_urls'] = json.loads(article['image_urls'])
                except (json.JSONDecodeError, TypeError):
                    article['image_urls'] = []
            else:
                article['image_urls'] = []
            
            # Tăng view count (background thread để không block response)
            import threading
            threading.Thread(target=update_view_count, args=(article_id,), daemon=True).start()
        
        cursor.close()
        conn.close()
        return article
        
    except Exception as e:
        print(f"❌ Error getting article: {e}")
        if conn:
            conn.close()
        return None


# ----------------------------------
# Lấy danh sách Articles
# ----------------------------------
def get_articles(status=None, user_id=None, limit=50, offset=0):
    """
    Lấy danh sách bài báo với filters
    
    Args:
        status: Lọc theo status ('draft', 'published', 'pending')
        user_id: Lọc theo người tạo
        limit: Số bài tối đa
        offset: Bỏ qua bao nhiêu bài
    """
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(dictionary=True)
        
        # Build query
        query = """
        SELECT a.id, a.title, a.summary, a.keywords, a.topic, 
               a.status, a.view_count, a.created_at, a.published_at,
               a.image_urls,
               u.email as author_email, u.full_name as author_name
        FROM articles a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND a.status = %s"
            params.append(status)
        
        if user_id:
            query += " AND a.user_id = %s"
            params.append(user_id)
        
        query += " ORDER BY a.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        articles = cursor.fetchall()
        
        # Parse JSON fields
        for article in articles:
            if article.get('image_urls'):
                try:
                    article['image_urls'] = json.loads(article['image_urls'])
                except:
                    article['image_urls'] = []
            else:
                article['image_urls'] = []
        
        cursor.close()
        conn.close()
        return articles
        
    except Exception as e:
        print(f"❌ Error getting articles: {e}")
        if conn:
            conn.close()
        return []


# ----------------------------------
# Cập nhật Article
# ----------------------------------
def update_article(article_id, user_id, **kwargs):
    """
    Cập nhật bài báo
    
    Args:
        article_id: ID bài báo
        user_id: ID người cập nhật
        **kwargs: title, content, summary, keywords, topic, description, status
    """
    conn = get_connection()
    if not conn:
        return False

    try:
        # Lấy nội dung cũ
        old_article = get_article_by_id(article_id)
        if not old_article:
            return False
        
        cursor = conn.cursor()
        
        # Build UPDATE query
        update_fields = []
        params = []
        
        for field in ['title', 'content', 'summary', 'keywords', 'topic', 'description', 'status']:
            if field in kwargs:
                update_fields.append(f"{field} = %s")
                params.append(kwargs[field])

        # Handle image_urls separately (needs JSON serialization)
        if 'image_urls' in kwargs:
            val = kwargs['image_urls']
            if isinstance(val, list):
                val = json.dumps(val)
            update_fields.append("image_urls = %s")
            params.append(val)

        if not update_fields:
            return False
        
        query = f"UPDATE articles SET {', '.join(update_fields)} WHERE id = %s"
        params.append(article_id)
        
        cursor.execute(query, params)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        print(f"✅ Article updated: ID={article_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating article: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Publish Article
# ----------------------------------
def publish_article(article_id, user_id):
    """Gửi bài báo để chờ duyệt (user) hoặc xuất bản (admin)"""
    conn = get_connection()
    if not conn:
        return False

    try:
        from database.user_model_simple import is_admin
        
        cursor = conn.cursor()
        
        # Kiểm tra nếu là admin → xuất bản ngay, user thường → chờ duyệt
        if is_admin(user_id):
            status = 'published'
            query = """
            UPDATE articles 
            SET status = 'published', published_at = NOW() 
            WHERE id = %s
            """
            log_action = 'published'
            message = "✅ Article published by admin"
        else:
            status = 'pending'
            query = """
            UPDATE articles 
            SET status = 'pending' 
            WHERE id = %s
            """
            log_action = 'pending'
            message = "✅ Article submitted for review"
        
        cursor.execute(query, (article_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        print(f"{message}: ID={article_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error publishing article: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Delete Article
# ----------------------------------
def delete_article(article_id):
    """Xóa bài báo (admin only)"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        query = "DELETE FROM articles WHERE id = %s"
        cursor.execute(query, (article_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        print(f"✅ Article deleted: ID={article_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting article: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Update View Count
# ----------------------------------
def update_view_count(article_id):
    """Tăng số lượt xem"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        query = "UPDATE articles SET view_count = view_count + 1 WHERE id = %s"
        cursor.execute(query, (article_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        if conn:
            conn.close()
        return False


# ----------------------------------
# Search Articles
# ----------------------------------
def search_articles(keyword, limit=20):
    """Tìm kiếm bài báo theo keyword"""
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT a.id, a.title, a.summary, a.keywords, a.created_at,
               u.email as author_email, u.full_name as author_name
        FROM articles a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.status = 'published'
        AND (a.title LIKE %s OR a.content LIKE %s OR a.keywords LIKE %s)
        ORDER BY a.created_at DESC
        LIMIT %s
        """
        search_term = f"%{keyword}%"
        cursor.execute(query, (search_term, search_term, search_term, limit))
        articles = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return articles
        
    except Exception as e:
        print(f"❌ Error searching articles: {e}")
        if conn:
            conn.close()
        return []


# ----------------------------------
# Get Article Stats
# ----------------------------------
def get_article_stats(user_id=None):
    """Lấy thống kê bài báo"""
    conn = get_connection()
    if not conn:
        return {}

    try:
        cursor = conn.cursor(dictionary=True)
        
        where_clause = f"WHERE user_id = {user_id}" if user_id else ""
        
        query = f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
            SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(view_count) as total_views
        FROM articles
        {where_clause}
        """
        cursor.execute(query)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        return stats or {}
        
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        if conn:
            conn.close()
        return {}


# ----------------------------------
# Get Top View Articles
# ----------------------------------
def get_top_view_articles(limit=4):
    """Lấy top bài viết đã xuất bản có lượt xem nhiều nhất"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = '''
        SELECT a.id, a.title, a.summary, a.keywords, a.topic, 
               a.status, a.view_count, a.created_at, a.published_at,
               a.image_urls,
               u.email as author_email, u.full_name as author_name
        FROM articles a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.status = 'published'
        ORDER BY a.view_count DESC, a.created_at DESC
        LIMIT %s
        '''
        cursor.execute(query, (limit,))
        articles = cursor.fetchall()
        for article in articles:
            if article.get('image_urls'):
                try:
                    article['image_urls'] = json.loads(article['image_urls'])
                except:
                    article['image_urls'] = []
            else:
                article['image_urls'] = []
        cursor.close()
        conn.close()
        return articles
    except Exception as e:
        print(f"❌ Error getting top view articles: {e}")
        if conn:
            conn.close()
        return []


# ----------------------------------
# Lấy bài viết liên quan (cùng topic)
# ----------------------------------
def get_related_articles(topic, exclude_id, limit=4):
    """Lấy bài viết liên quan cùng topic bằng query trực tiếp (nhanh hơn load 200 rồi filter).
    Dùng index idx_articles_status_topic.
    """
    if not topic:
        return []
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, title, summary, topic, image_urls,
                   view_count, published_at, created_at
            FROM articles
            WHERE status = 'published'
              AND topic = %s
              AND id != %s
            ORDER BY published_at DESC, created_at DESC
            LIMIT %s
            """,
            (topic, exclude_id, limit),
        )
        articles = cursor.fetchall() or []
        for article in articles:
            if article.get('image_urls'):
                try:
                    article['image_urls'] = json.loads(article['image_urls'])
                except Exception:
                    article['image_urls'] = []
            else:
                article['image_urls'] = []
        cursor.close()
        conn.close()
        return articles
    except Exception as e:
        print(f"❌ Error getting related articles: {e}")
        if conn:
            conn.close()
        return []



def get_all_articles_admin(status=None, flagged_only=False, keyword=None, limit=100, offset=0):
    """Lấy tất cả bài viết cho admin với filter"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        conditions = []
        params = []
        if status:
            conditions.append("a.status = %s")
            params.append(status)
        if flagged_only:
            conditions.append("a.flagged = 1")
        if keyword:
            conditions.append("(a.title LIKE %s OR a.summary LIKE %s OR a.keywords LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"""
        SELECT a.id, a.title, a.summary, a.status, a.flagged, a.flag_reason,
               a.view_count, a.created_at, a.published_at, a.topic, a.image_urls,
               a.user_id, a.magazine_id,
               u.email AS author_email, u.full_name AS author_name,
               m.title AS magazine_title
        FROM articles a
        LEFT JOIN users u ON a.user_id = u.id
        LEFT JOIN magazines m ON a.magazine_id = m.id
        {where}
        ORDER BY a.created_at DESC
        LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = cursor.fetchall()
        for r in rows:
            if r.get('image_urls'):
                try:
                    r['image_urls'] = json.loads(r['image_urls'])
                except Exception:
                    r['image_urls'] = []
            else:
                r['image_urls'] = []
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ Error get_all_articles_admin: {e}")
        if conn:
            conn.close()
        return []


def count_all_articles_admin(status=None, flagged_only=False, keyword=None):
    """Đếm tổng số bài viết thỏa điều kiện"""
    conn = get_connection()
    if not conn:
        return 0
    try:
        cursor = conn.cursor()
        conditions = []
        params = []
        if status:
            conditions.append("status = %s")
            params.append(status)
        if flagged_only:
            conditions.append("flagged = 1")
        if keyword:
            conditions.append("(title LIKE %s OR summary LIKE %s OR keywords LIKE %s)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cursor.execute(f"SELECT COUNT(*) FROM articles {where}", params)
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        print(f"❌ Error count_all_articles_admin: {e}")
        if conn:
            conn.close()
        return 0


# ----------------------------------
# Admin: Ẩn / Hiện bài viết
# ----------------------------------
def hide_article(article_id):
    """Ẩn bài viết (set status='hidden')"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE articles SET status = 'hidden' WHERE id = %s", (article_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error hide_article: {e}")
        if conn:
            conn.close()
        return False


def unhide_article(article_id):
    """Khôi phục bài viết bị ẩn (set status='published')"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE articles SET status = 'published' WHERE id = %s", (article_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error unhide_article: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Admin: Gắn cờ / Bỏ cờ bài viết
# ----------------------------------
def flag_article(article_id, reason=''):
    """Gắn cờ bài viết cần kiểm duyệt"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE articles SET flagged = 1, flag_reason = %s WHERE id = %s",
            (reason or None, article_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error flag_article: {e}")
        if conn:
            conn.close()
        return False


def unflag_article(article_id):
    """Bỏ cờ bài viết"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE articles SET flagged = 0, flag_reason = NULL WHERE id = %s",
            (article_id,)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error unflag_article: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Admin: Thống kê nội dung
# ----------------------------------
def get_content_stats():
    """Thống kê tổng quan nội dung cho admin"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
              COUNT(*) AS total,
              SUM(status='published') AS published,
              SUM(status='draft') AS draft,
              SUM(status='pending') AS pending,
              SUM(status='hidden') AS hidden,
              SUM(flagged=1) AS flagged
            FROM articles
        """)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row or {}
    except Exception as e:
        print(f"❌ Error get_content_stats: {e}")
        if conn:
            conn.close()
        return {}
