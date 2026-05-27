"""
Schedule Model - Quản lý lịch tự động tạo bài viết
"""
from database.db_simple import get_connection
from datetime import datetime


def create_schedules_table():
    """Tạo bảng magazine_schedules nếu chưa có, migrate cột mới nếu thiếu"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        # Tạo bảng mới với đầy đủ cột
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS magazine_schedules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                magazine_id INT NOT NULL,
                user_id INT NOT NULL,
                category_name VARCHAR(255) DEFAULT NULL,
                keywords VARCHAR(255) DEFAULT NULL,
                frequency VARCHAR(20) NOT NULL DEFAULT 'daily',
                days_of_week VARCHAR(50) DEFAULT '',
                hour INT NOT NULL DEFAULT 8,
                minute INT NOT NULL DEFAULT 0,
                interval_minutes INT NOT NULL DEFAULT 0,
                num_articles INT NOT NULL DEFAULT 2,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                last_run TIMESTAMP NULL,
                next_run TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (magazine_id) REFERENCES magazines(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_magazine (magazine_id),
                INDEX idx_user (user_id),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()

        # Migration: thêm cột interval_minutes nếu bảng cũ chưa có
        try:
            cursor.execute("""
                ALTER TABLE magazine_schedules
                ADD COLUMN IF NOT EXISTS interval_minutes INT NOT NULL DEFAULT 0
            """)
            conn.commit()
        except Exception:
            pass  # Cột đã tồn tại hoặc DB không hỗ trợ IF NOT EXISTS

        # Migration: thêm cột category_name nếu bảng cũ chưa có
        try:
            cursor.execute("""
                ALTER TABLE magazine_schedules
                ADD COLUMN IF NOT EXISTS category_name VARCHAR(255) DEFAULT NULL AFTER user_id
            """)
            conn.commit()
        except Exception:
            try:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'magazine_schedules'
                      AND COLUMN_NAME = 'category_name'
                """)
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("""
                        ALTER TABLE magazine_schedules
                        ADD COLUMN category_name VARCHAR(255) DEFAULT NULL AFTER user_id
                    """)
                    conn.commit()
            except Exception:
                pass

        # Migration: thêm cột keywords nếu bảng cũ chưa có
        try:
            cursor.execute("""
                ALTER TABLE magazine_schedules
                ADD COLUMN IF NOT EXISTS keywords VARCHAR(255) DEFAULT NULL AFTER category_name
            """)
            conn.commit()
        except Exception:
            try:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'magazine_schedules'
                      AND COLUMN_NAME = 'keywords'
                """)
                exists = cursor.fetchone()[0]
                if not exists:
                    cursor.execute("""
                        ALTER TABLE magazine_schedules
                        ADD COLUMN keywords VARCHAR(255) DEFAULT NULL AFTER category_name
                    """)
                    conn.commit()
            except Exception:
                pass

        # Migration: đổi frequency từ ENUM sang VARCHAR nếu cần
        try:
            cursor.execute("""
                ALTER TABLE magazine_schedules
                MODIFY COLUMN frequency VARCHAR(20) NOT NULL DEFAULT 'daily'
            """)
            conn.commit()
        except Exception:
            pass

        cursor.close()
        conn.close()
        print("[OK] Table magazine_schedules ready.")
        return True
    except Exception as e:
        print(f"[ERR] create_schedules_table: {e}")
        if conn:
            conn.close()
        return False


def create_schedule(magazine_id, user_id, frequency, hour, minute, num_articles,
                    category_name=None,
                    days_of_week='', interval_minutes=0,
                    keywords=None):
    """Tạo lịch mới cho tạp chí"""
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO magazine_schedules
            (magazine_id, user_id, category_name, keywords, frequency, days_of_week, hour, minute,
             interval_minutes, num_articles, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
        """, (magazine_id, user_id, category_name, keywords, frequency, days_of_week, hour, minute,
               interval_minutes, num_articles))
        conn.commit()
        schedule_id = cursor.lastrowid
        cursor.close()
        conn.close()
        print(f"[OK] Schedule created: ID={schedule_id}, freq={frequency}, interval={interval_minutes}m")
        return schedule_id
    except Exception as e:
        print(f"[ERR] create_schedule: {e}")
        if conn:
            conn.close()
        return None


def get_schedules_by_magazine(magazine_id):
    """Lấy danh sách lịch của tạp chí"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM magazine_schedules
            WHERE magazine_id = %s
            ORDER BY created_at DESC
        """, (magazine_id,))
        schedules = cursor.fetchall()
        cursor.close()
        conn.close()
        return schedules
    except Exception as e:
        print(f"[ERR] get_schedules_by_magazine: {e}")
        if conn:
            conn.close()
        return []


def get_all_active_schedules():
    """Lấy tất cả lịch đang active (dùng cho scheduler)"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, m.title as magazine_title,
                   COALESCE(s.category_name, m.topic) as topic,
                   COALESCE(s.keywords, m.keywords) as keywords,
                   m.description,
                   m.user_id as magazine_owner_id
            FROM magazine_schedules s
            JOIN magazines m ON s.magazine_id = m.id
            WHERE s.is_active = 1 AND m.status = 'active'
        """)
        schedules = cursor.fetchall()
        cursor.close()
        conn.close()
        return schedules
    except Exception as e:
        print(f"[ERR] get_all_active_schedules: {e}")
        if conn:
            conn.close()
        return []


def update_schedule_last_run(schedule_id):
    """Cập nhật thời gian chạy cuối"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE magazine_schedules SET last_run = NOW() WHERE id = %s
        """, (schedule_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERR] update_schedule_last_run: {e}")
        if conn:
            conn.close()
        return False


def toggle_schedule(schedule_id, user_id):
    """Bật/tắt lịch"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE magazine_schedules
            SET is_active = 1 - is_active
            WHERE id = %s AND user_id = %s
        """, (schedule_id, user_id))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected > 0
    except Exception as e:
        print(f"[ERR] toggle_schedule: {e}")
        if conn:
            conn.close()
        return False


def delete_schedule(schedule_id, user_id):
    """Xóa lịch"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM magazine_schedules WHERE id = %s AND user_id = %s
        """, (schedule_id, user_id))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected > 0
    except Exception as e:
        print(f"[ERR] delete_schedule: {e}")
        if conn:
            conn.close()
        return False


def get_schedule_by_id(schedule_id):
    """Lấy thông tin lịch theo ID"""
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM magazine_schedules WHERE id = %s", (schedule_id,))
        schedule = cursor.fetchone()
        cursor.close()
        conn.close()
        return schedule
    except Exception as e:
        print(f"[ERR] get_schedule_by_id: {e}")
        if conn:
            conn.close()
        return None


def get_schedules_by_user(user_id):
    """Lấy tất cả lịch của một user, kèm tên tạp chí"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, m.title as magazine_title
            FROM magazine_schedules s
            JOIN magazines m ON s.magazine_id = m.id
            WHERE s.user_id = %s
            ORDER BY s.created_at DESC
        """, (user_id,))
        schedules = cursor.fetchall() or []
        cursor.close()
        conn.close()
        return schedules
    except Exception as e:
        print(f"[ERR] get_schedules_by_user: {e}")
        if conn:
            conn.close()
        return []


def update_schedule(schedule_id, user_id, category_name, keywords, frequency,
                    hour, minute, num_articles, days_of_week, interval_minutes):
    """Cập nhật thông tin lịch (chỉnh sửa)"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE magazine_schedules
            SET category_name=%s, keywords=%s, frequency=%s,
                hour=%s, minute=%s, num_articles=%s,
                days_of_week=%s, interval_minutes=%s
            WHERE id=%s AND user_id=%s
        """, (category_name, keywords or None, frequency, hour, minute,
              num_articles, days_of_week, interval_minutes, schedule_id, user_id))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected > 0
    except Exception as e:
        print(f"[ERR] update_schedule: {e}")
        if conn:
            conn.close()
        return False
