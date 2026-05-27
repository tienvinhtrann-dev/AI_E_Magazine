"""
Magazine Model - Quản lý tạp chí AI
"""
from database.db_simple import get_connection
from datetime import datetime
from collections import Counter
import json


_ARTICLE_MAGAZINE_INDEXES_READY = False


def _ensure_article_magazine_indexes():
    global _ARTICLE_MAGAZINE_INDEXES_READY
    if _ARTICLE_MAGAZINE_INDEXES_READY:
        return True

    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()

        cursor.execute("SHOW INDEX FROM articles WHERE Key_name = 'idx_articles_magazine_created'")
        has_mag_created = bool(cursor.fetchall())

        cursor.execute("SHOW INDEX FROM articles WHERE Key_name = 'idx_articles_magazine_topic'")
        has_mag_topic = bool(cursor.fetchall())

        if not has_mag_created:
            cursor.execute(
                "ALTER TABLE articles ADD INDEX idx_articles_magazine_created (magazine_id, created_at)"
            )
            conn.commit()
            print("[OK] Added idx_articles_magazine_created")

        if not has_mag_topic:
            cursor.execute(
                "ALTER TABLE articles ADD INDEX idx_articles_magazine_topic (magazine_id, topic)"
            )
            conn.commit()
            print("[OK] Added idx_articles_magazine_topic")

        cursor.close()
        conn.close()
        _ARTICLE_MAGAZINE_INDEXES_READY = True
        return True
    except Exception as e:
        print(f"[WARN] _ensure_article_magazine_indexes: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return False


def ensure_magazines_schema():
    """Tạo bảng magazines nếu chưa có, và đảm bảo đầy đủ các cột phụ trợ."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()

        # Tạo bảng magazines nếu chưa tồn tại
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS magazines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(500) NOT NULL,
                slug VARCHAR(255) NULL,
                theme VARCHAR(50) NOT NULL DEFAULT 'default',
                article_theme VARCHAR(50) NOT NULL DEFAULT 'default',
                topic VARCHAR(255),
                description TEXT,
                keywords VARCHAR(500),
                num_articles INT NOT NULL DEFAULT 3,
                categories_config TEXT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_user_id (user_id),
                INDEX idx_status (status),
                INDEX idx_slug (slug)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()

        # Thêm cột magazine_id vào articles nếu chưa có
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'articles'
              AND COLUMN_NAME = 'magazine_id'
        """)
        row = cursor.fetchone()
        if not (row and row[0] > 0):
            cursor.execute(
                "ALTER TABLE articles ADD COLUMN magazine_id INT NULL,"
                "ADD INDEX idx_magazine_id (magazine_id)"
            )
            conn.commit()
            print("[OK] Added magazine_id column to articles")

        # Thêm cột categories_config nếu chưa có
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'magazines'
              AND COLUMN_NAME = 'categories_config'
        """)
        row = cursor.fetchone()
        has_categories_column = bool(row and row[0] > 0)

        if not has_categories_column:
            cursor.execute("ALTER TABLE magazines ADD COLUMN categories_config TEXT NULL")
            conn.commit()
            print("[OK] Added categories_config column to magazines")

        # Thêm cột slug nếu chưa có (dùng cho URL thân thiện)
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'magazines'
              AND COLUMN_NAME = 'slug'
        """)
        row = cursor.fetchone()
        has_slug_column = bool(row and row[0] > 0)

        if not has_slug_column:
            cursor.execute("ALTER TABLE magazines ADD COLUMN slug VARCHAR(255) NULL AFTER title")
            conn.commit()
            print("[OK] Added slug column to magazines")

        # Thêm cột theme nếu chưa có (chọn giao diện tạp chí)
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'magazines'
              AND COLUMN_NAME = 'theme'
        """)
        row = cursor.fetchone()
        has_theme_column = bool(row and row[0] > 0)

        if not has_theme_column:
            cursor.execute(
                "ALTER TABLE magazines ADD COLUMN theme VARCHAR(50) NOT NULL DEFAULT 'default' AFTER slug"
            )
            conn.commit()
            print("[OK] Added theme column to magazines")

        # Thêm cột article_theme nếu chưa có (giao diện popup bài viết)
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'magazines'
              AND COLUMN_NAME = 'article_theme'
        """)
        row = cursor.fetchone()
        has_article_theme_column = bool(row and row[0] > 0)

        if not has_article_theme_column:
            cursor.execute(
                "ALTER TABLE magazines ADD COLUMN article_theme VARCHAR(50) NOT NULL DEFAULT 'default' AFTER theme"
            )
            conn.commit()
            print("[OK] Added article_theme column to magazines")

        # Thêm các cột cài đặt tạp chí nếu chưa có
        for col_name, col_def in [
            ('custom_domain', 'VARCHAR(255) NULL'),
            ('language',      "VARCHAR(10) NOT NULL DEFAULT 'vi'"),
            ('comments_locked', 'TINYINT(1) NOT NULL DEFAULT 0'),
            ('timezone',      "VARCHAR(50) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh'"),
        ]:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'magazines' AND COLUMN_NAME = %s
            """, (col_name,))
            if not cursor.fetchone()[0]:
                cursor.execute(f"ALTER TABLE magazines ADD COLUMN {col_name} {col_def}")
                conn.commit()
                print(f"[OK] Added {col_name} column to magazines")

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERR] ensure_magazines_schema: {e}")
        if conn:
            conn.close()
        return False


def create_magazine(user_id, title, topic, keywords, description='', num_articles=3, categories_config=None, slug=None):
    """Tạo tạp chí mới, trả về magazine_id"""
    if not ensure_magazines_schema():
        print("[WARN] ensure_magazines_schema failed, continue creating magazine")

    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        categories_json = json.dumps(categories_config or [], ensure_ascii=False)

        # Cột theme có default 'default' nên không cần truyền vào đây
        cursor.execute(
            """
            INSERT INTO magazines (user_id, title, slug, topic, description, keywords, num_articles, categories_config)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, title, slug, topic, description, keywords, num_articles, categories_json),
        )

        conn.commit()
        magazine_id = cursor.lastrowid
        cursor.close()
        conn.close()
        print(f"[OK] Magazine created: ID={magazine_id}, Title={title}")
        return magazine_id
    except Exception as e:
        print(f"[ERR] Error creating magazine: {e}")
        if conn:
            conn.close()
        return None


def get_magazine_by_id(magazine_id):
    """Lấy thông tin tạp chí theo ID"""
    conn = get_connection()
    if not conn:
        return None
    try:
        # Dùng buffered=True để tránh lỗi "Unread result found" khi đóng cursor/connection
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("""
            SELECT m.*, u.email as owner_email, u.full_name as owner_name,
                   COUNT(a.id) as article_count
            FROM magazines m
            LEFT JOIN users u ON m.user_id = u.id
            LEFT JOIN articles a ON a.magazine_id = m.id
            WHERE m.id = %s
            GROUP BY m.id
        """, (magazine_id,))
        magazine = cursor.fetchone()
        cursor.close()
        conn.close()
        return magazine
    except Exception as e:
        print(f"[ERR] Error getting magazine: {e}")
        if conn:
            conn.close()
        return None


def get_magazine_by_slug(slug):
    """Lấy thông tin tạp chí theo slug (URL thân thiện)"""
    if not slug:
        return None
    conn = get_connection()
    if not conn:
        return None
    try:
        # Dùng buffered=True để đọc hết kết quả trước khi đóng để tránh "Unread result found"
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("""
            SELECT m.*, u.email as owner_email, u.full_name as owner_name,
                   COUNT(a.id) as article_count
            FROM magazines m
            LEFT JOIN users u ON m.user_id = u.id
            LEFT JOIN articles a ON a.magazine_id = m.id
            WHERE m.slug = %s
            GROUP BY m.id
        """, (slug,))
        magazine = cursor.fetchone()
        cursor.close()
        conn.close()
        return magazine
    except Exception as e:
        print(f"[ERR] Error getting magazine by slug: {e}")
        if conn:
            conn.close()
        return None


def get_magazines_by_user(user_id):
    """Lấy danh sách tạp chí của user"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT m.*, COUNT(a.id) as article_count
            FROM magazines m
            LEFT JOIN articles a ON a.magazine_id = m.id
            WHERE m.user_id = %s
            GROUP BY m.id
            ORDER BY m.created_at DESC
        """, (user_id,))
        magazines = cursor.fetchall()
        cursor.close()
        conn.close()
        return magazines
    except Exception as e:
        print(f"[ERR] Error getting magazines: {e}")
        if conn:
            conn.close()
        return []


def get_all_magazines(limit=20):
    """Lấy tất cả tạp chí active"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT m.*, u.full_name as owner_name, u.email as owner_email,
                   COUNT(a.id) as article_count
            FROM magazines m
            LEFT JOIN users u ON m.user_id = u.id
            LEFT JOIN articles a ON a.magazine_id = m.id
            WHERE m.status = 'active'
            GROUP BY m.id
            ORDER BY m.created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        magazines = cursor.fetchall()
        cursor.close()
        conn.close()
        return magazines
    except Exception as e:
        print(f"[ERR] Error getting all magazines: {e}")
        if conn:
            conn.close()
        return []


def is_magazine_slug_taken(slug, exclude_id=None):
    """Kiểm tra slug đã được dùng cho tạp chí khác chưa."""
    if not slug:
        return False
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        if exclude_id is not None:
            cursor.execute(
                "SELECT COUNT(*) FROM magazines WHERE slug = %s AND id <> %s",
                (slug, exclude_id),
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM magazines WHERE slug = %s",
                (slug,),
            )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return bool(row and row[0] > 0)
    except Exception as e:
        print(f"[ERR] is_magazine_slug_taken: {e}")
        if conn:
            conn.close()
        return False


def update_magazine_basic(magazine_id, title, slug, topic, description, keywords, theme=None, article_theme=None):
    """Cập nhật các thông tin cơ bản của tạp chí.

    Chỉ cho phép sửa các trường text chính, không đụng tới categories_config để tránh
    ảnh hưởng pipeline AI.
    """
    if not magazine_id:
        return False

    # Không cho slug rỗng, nhưng cho phép NULL trong DB nếu người dùng xóa
    slug_to_save = slug.strip() if isinstance(slug, str) else None

    if slug_to_save and is_magazine_slug_taken(slug_to_save, exclude_id=magazine_id):
        # Slug trùng, trả về False để route tự flash lỗi cụ thể
        print(f"[WARN] update_magazine_basic: slug '{slug_to_save}' is taken")
        return False

    # Theme/article_theme: nếu None thì giữ nguyên giá trị cũ
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()

        if theme is None and article_theme is None:
            cursor.execute(
                """
                UPDATE magazines
                SET title = %s,
                    slug = %s,
                    topic = %s,
                    description = %s,
                    keywords = %s
                WHERE id = %s
                """,
                (title, slug_to_save, topic, description, keywords, magazine_id),
            )
        elif article_theme is None:
            cursor.execute(
                """
                UPDATE magazines
                SET title = %s,
                    slug = %s,
                    topic = %s,
                    description = %s,
                    keywords = %s,
                    theme = %s
                WHERE id = %s
                """,
                (title, slug_to_save, topic, description, keywords, theme, magazine_id),
            )
        elif theme is None:
            cursor.execute(
                """
                UPDATE magazines
                SET title = %s,
                    slug = %s,
                    topic = %s,
                    description = %s,
                    keywords = %s,
                    article_theme = %s
                WHERE id = %s
                """,
                (title, slug_to_save, topic, description, keywords, article_theme, magazine_id),
            )
        else:
            cursor.execute(
                """
                UPDATE magazines
                SET title = %s,
                    slug = %s,
                    topic = %s,
                    description = %s,
                    keywords = %s,
                    theme = %s,
                    article_theme = %s
                WHERE id = %s
                """,
                (title, slug_to_save, topic, description, keywords, theme, article_theme, magazine_id),
            )
        conn.commit()
        affected = cursor.rowcount
        print(f"[DEBUG] update_magazine_basic: mag_id={magazine_id}, theme={theme!r}, article_theme={article_theme!r}, rowcount={affected}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERR] update_magazine_basic: {e}")
        if conn:
            conn.close()
        return False


def get_articles_by_magazine(magazine_id):
    """Lấy danh sách bài viết của một tạp chí"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM articles
            WHERE magazine_id = %s
            ORDER BY created_at DESC
        """, (magazine_id,))
        articles = cursor.fetchall()

        # Parse các trường JSON (image_urls, source_urls) để dùng tiện trong template
        for art in articles:
            if art.get('image_urls'):
                try:
                    art['image_urls'] = json.loads(art['image_urls'])
                except Exception:
                    art['image_urls'] = []
            else:
                art['image_urls'] = []

            if art.get('source_urls'):
                try:
                    art['source_urls'] = json.loads(art['source_urls'])
                except Exception:
                    art['source_urls'] = []
            else:
                art['source_urls'] = []

        cursor.close()
        conn.close()
        return articles
    except Exception as e:
        print(f"[ERR] Error getting articles for magazine: {e}")
        if conn:
            conn.close()
        return []
def get_article_previews_by_magazine(magazine_id, limit=None, offset=0):
    """Lấy dữ liệu preview bài viết cho trang tạp chí (không lấy content để giảm tải)."""
    _ensure_article_magazine_indexes()
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT id, user_id, magazine_id, title, summary, keywords, topic,
                   image_urls, source_urls, status, view_count, created_at
            FROM articles
            WHERE magazine_id = %s
            ORDER BY created_at DESC
        """
        params = [magazine_id]
        if isinstance(limit, int) and limit > 0:
            sql += " LIMIT %s"
            params.append(limit)
            if isinstance(offset, int) and offset > 0:
                sql += " OFFSET %s"
                params.append(offset)
        cursor.execute(sql, tuple(params))
        articles = cursor.fetchall()

        for art in articles:
            if art.get('image_urls'):
                try:
                    art['image_urls'] = json.loads(art['image_urls'])
                except Exception:
                    art['image_urls'] = []
            else:
                art['image_urls'] = []

            if art.get('source_urls'):
                try:
                    art['source_urls'] = json.loads(art['source_urls'])
                except Exception:
                    art['source_urls'] = []
            else:
                art['source_urls'] = []

        cursor.close()
        conn.close()
        return articles
    except Exception as e:
        print(f"[ERR] Error getting article previews for magazine: {e}")
        if conn:
            conn.close()
        return []


def get_article_topic_counts_by_magazine(magazine_id):
    """Lấy số lượng bài viết theo topic để dựng menu danh mục nhanh hơn."""
    _ensure_article_magazine_indexes()
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(topic), ''), '') AS topic_name, COUNT(*) AS article_count
            FROM articles
            WHERE magazine_id = %s
            GROUP BY topic_name
            ORDER BY article_count DESC, topic_name ASC
            """,
            (magazine_id,),
        )
        rows = cursor.fetchall() or []
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[ERR] Error getting article topic counts for magazine: {e}")
        if conn:
            conn.close()
        return []


def save_article_to_magazine(magazine_id, user_id, title, content, summary, keywords, topic, image_url='', image_urls=None, source_urls=None):
    """Lưu bài viết AI vào tạp chí (tự động published).

    Ghi chú: tránh chống trùng quá gắt ở tầng DB để số bài
    tạo ra luôn khớp với số bài hiển thị. Việc tránh trùng
    nguồn đã được xử lý ở tầng crawl/generate.
    """
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()

        images_payload = []
        if isinstance(image_urls, list):
            images_payload = [u for u in image_urls if isinstance(u, str) and u.strip().startswith('http')]
        if not images_payload and image_url and isinstance(image_url, str) and image_url.strip().startswith('http'):
            images_payload = [image_url.strip()]

        sources_payload = []
        if isinstance(source_urls, list):
            sources_payload = [u for u in source_urls if isinstance(u, str) and u.strip().startswith('http')]

        cursor.execute(
            """
            INSERT INTO articles
                        (user_id, magazine_id, title, content, summary, keywords, topic, source_urls, image_urls, status, published_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'published', NOW())
        """,
            (
                user_id,
                magazine_id,
                title,
                content,
                summary,
                keywords,
                topic,
                json.dumps(sources_payload, ensure_ascii=False),
                json.dumps(images_payload, ensure_ascii=False),
            ),
        )
        conn.commit()
        article_id = cursor.lastrowid
        cursor.close()
        conn.close()
        print(f"[OK] Article saved to magazine: ID={article_id}")
        return article_id
    except Exception as e:
        print(f"[ERR] Error saving article to magazine: {e}")
        if conn:
            conn.close()
        return None


def delete_magazine(magazine_id, user_id):
    """Xóa tạp chí (chỉ chủ sở hữu)"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM magazines WHERE id = %s AND user_id = %s",
            (magazine_id, user_id)
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected > 0
    except Exception as e:
        print(f"[ERR] Error deleting magazine: {e}")
        if conn:
            conn.close()
        return False


def update_magazine_settings(magazine_id, user_id, title, slug,
                              custom_domain=None, language='vi',
                              comments_locked=0, timezone='Asia/Ho_Chi_Minh'):
    """Lưu cài đặt tạp chí từ tab Cài đặt dashboard."""
    if not magazine_id:
        return False, 'Tạp chí không hợp lệ.'
    slug_to_save = slug.strip() if isinstance(slug, str) and slug.strip() else None
    if slug_to_save and is_magazine_slug_taken(slug_to_save, exclude_id=magazine_id):
        return False, 'Slug/tên miền này đã được dùng bởi tạp chí khác.'
    conn = get_connection()
    if not conn:
        return False, 'Lỗi kết nối database.'
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE magazines
            SET title = %s, slug = %s, custom_domain = %s,
                language = %s, comments_locked = %s, timezone = %s
            WHERE id = %s AND user_id = %s
        """, (title, slug_to_save, custom_domain or None,
               language, int(bool(comments_locked)),
               timezone, magazine_id, user_id))
        conn.commit()
        ok = cursor.rowcount > 0
        cursor.close()
        conn.close()
        return ok, None
    except Exception as e:
        print(f"[ERR] update_magazine_settings: {e}")
        if conn:
            conn.close()
        return False, str(e)


def update_magazine_status(magazine_id, user_id, status):
    """Cập nhật trạng thái tạp chí (active / archived / draft)."""
    if status not in ("active", "archived", "draft"):
        return False
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE magazines SET status = %s WHERE id = %s AND user_id = %s",
            (status, magazine_id, user_id),
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected > 0
    except Exception as e:
        print(f"[ERR] update_magazine_status: {e}")
        if conn:
            conn.close()
        return False

