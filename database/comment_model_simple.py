"""
Comment Model - Quản lý bình luận bài viết
"""
from database.db_simple import get_connection
from datetime import datetime

# Cache schema detection - chỉ kiểm tra 1 lần khi server khởi động
_schema_cache = {}

def _detect_comments_schema():
    """Kiểm tra và cache schema của bảng comments một lần duy nhất."""
    if 'checked' in _schema_cache:
        return _schema_cache
    conn = get_connection()
    if not conn:
        _schema_cache['checked'] = True
        _schema_cache['has_parent_id'] = False
        _schema_cache['has_likes_count'] = False
        return _schema_cache
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW COLUMNS FROM comments LIKE 'parent_id'")
        _schema_cache['has_parent_id'] = cursor.fetchone() is not None
        cursor.execute("SHOW COLUMNS FROM comments LIKE 'likes_count'")
        _schema_cache['has_likes_count'] = cursor.fetchone() is not None
        _schema_cache['checked'] = True
        cursor.close()
    except Exception:
        _schema_cache['has_parent_id'] = False
        _schema_cache['has_likes_count'] = False
        _schema_cache['checked'] = True
    finally:
        conn.close()
    return _schema_cache

# Thêm bình luận mới
def add_comment(article_id, user_id, content):
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO comments (article_id, user_id, content, created_at)
        VALUES (%s, %s, %s, %s)
        """
        now = datetime.now()
        cursor.execute(query, (article_id, user_id, content, now))
        conn.commit()
        comment_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return comment_id
    except Exception as e:
        print(f"❌ Error add_comment: {e}")
        if conn:
            conn.close()
        return None

# Lấy danh sách bình luận theo bài viết (mới nhất trước)
def get_comments_by_article(article_id, limit=100, user_id=None):
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        schema = _detect_comments_schema()
        has_parent_id   = schema.get('has_parent_id', False)
        has_likes_count = schema.get('has_likes_count', False)
        
        if has_parent_id and has_likes_count:
            # Nếu đã có đầy đủ cột, dùng query mới với like và reply
            if user_id:
                query = """
                SELECT c.*, u.email as user_email, u.full_name as user_name,
                       COALESCE(c.likes_count, 0) as likes_count,
                       EXISTS(SELECT 1 FROM comment_likes WHERE comment_id = c.id AND user_id = %s) as user_liked
                FROM comments c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.article_id = %s AND (c.parent_id IS NULL OR c.parent_id = 0)
                ORDER BY c.created_at DESC
                LIMIT %s
                """
                cursor.execute(query, (user_id, article_id, limit))
            else:
                query = """
                SELECT c.*, u.email as user_email, u.full_name as user_name,
                       COALESCE(c.likes_count, 0) as likes_count, 0 as user_liked
                FROM comments c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.article_id = %s AND (c.parent_id IS NULL OR c.parent_id = 0)
                ORDER BY c.created_at DESC
                LIMIT %s
                """
                cursor.execute(query, (article_id, limit))
            comments = cursor.fetchall()
            
            # Lấy câu trả lời cho mỗi bình luận
            for comment in comments:
                comment['replies'] = get_comment_replies(comment['id'], user_id)
        else:
            # Nếu chưa có cột, dùng query đơn giản (version cũ)
            query = """
            SELECT c.*, u.email as user_email, u.full_name as user_name,
                   0 as likes_count, 0 as user_liked
            FROM comments c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.article_id = %s
            ORDER BY c.created_at DESC
            LIMIT %s
            """
            cursor.execute(query, (article_id, limit))
            comments = cursor.fetchall()
            # Không có replies vì chưa có cột parent_id
            for comment in comments:
                comment['replies'] = []
        
        cursor.close()
        conn.close()
        return comments
    except Exception as e:
        print(f"❌ Error get_comments_by_article: {e}")
        if conn:
            conn.close()
        return []

# Lấy câu trả lời của bình luận
def get_comment_replies(parent_id, user_id=None):
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        if user_id:
            query = """
            SELECT c.*, u.email as user_email, u.full_name as user_name,
                   COALESCE(c.likes_count, 0) as likes_count,
                   EXISTS(SELECT 1 FROM comment_likes WHERE comment_id = c.id AND user_id = %s) as user_liked
            FROM comments c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.parent_id = %s
            ORDER BY c.created_at ASC
            """
            cursor.execute(query, (user_id, parent_id))
        else:
            query = """
            SELECT c.*, u.email as user_email, u.full_name as user_name,
                   COALESCE(c.likes_count, 0) as likes_count, 0 as user_liked
            FROM comments c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.parent_id = %s
            ORDER BY c.created_at ASC
            """
            cursor.execute(query, (parent_id,))
        replies = cursor.fetchall()
        cursor.close()
        conn.close()
        return replies
    except Exception as e:
        print(f"❌ Error get_comment_replies: {e}")
        if conn:
            conn.close()
        return []

# Thích bình luận
def like_comment(comment_id, user_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        schema = _detect_comments_schema()
        has_likes_count = schema.get('has_likes_count', False)
        
        if not has_likes_count:
            # Chưa có cột likes_count, không thể like
            cursor.close()
            conn.close()
            return False
        
        # Kiểm tra đã like chưa
        cursor.execute("SELECT id FROM comment_likes WHERE comment_id = %s AND user_id = %s", (comment_id, user_id))
        if cursor.fetchone():
            # Đã like rồi, bỏ like
            cursor.execute("DELETE FROM comment_likes WHERE comment_id = %s AND user_id = %s", (comment_id, user_id))
            cursor.execute("UPDATE comments SET likes_count = GREATEST(likes_count - 1, 0) WHERE id = %s", (comment_id,))
            liked = False
        else:
            # Chưa like, thêm like
            cursor.execute("INSERT INTO comment_likes (comment_id, user_id) VALUES (%s, %s)", (comment_id, user_id))
            cursor.execute("UPDATE comments SET likes_count = likes_count + 1 WHERE id = %s", (comment_id,))
            liked = True
        conn.commit()
        
        # Lấy số lượt thích mới
        cursor.execute("SELECT COALESCE(likes_count, 0) FROM comments WHERE id = %s", (comment_id,))
        result = cursor.fetchone()
        likes_count = result[0] if result else 0
        
        cursor.close()
        conn.close()
        return {'success': True, 'liked': liked, 'likes_count': likes_count}
    except Exception as e:
        print(f"❌ Error like_comment: {e}")
        if conn:
            conn.close()
        return False

# Trả lời bình luận
def reply_comment(article_id, parent_id, user_id, content):
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        schema = _detect_comments_schema()
        has_parent_id = schema.get('has_parent_id', False)
        
        if has_parent_id:
            # Có cột parent_id, thêm reply
            query = """
            INSERT INTO comments (article_id, user_id, content, created_at, parent_id, likes_count)
            VALUES (%s, %s, %s, %s, %s, 0)
            """
            now = datetime.now()
            cursor.execute(query, (article_id, user_id, content, now, parent_id))
        else:
            # Chưa có cột parent_id, không thể reply
            cursor.close()
            conn.close()
            return None
        
        conn.commit()
        comment_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return comment_id
    except Exception as e:
        print(f"❌ Error reply_comment: {e}")
        if conn:
            conn.close()
        return None
