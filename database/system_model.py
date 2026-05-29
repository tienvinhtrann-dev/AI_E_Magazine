"""
System Model - Admin system management: settings, logs, schedules
"""
from database.db_simple import get_connection, DB_CONFIG
import json


# ----------------------------------
# Khởi tạo bảng system_settings
# ----------------------------------
def init_settings_table():
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                `key`   VARCHAR(100) NOT NULL PRIMARY KEY,
                `value` TEXT,
                `label` VARCHAR(255),
                `type`  VARCHAR(20) DEFAULT 'text',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        # Seed mặc định nếu chưa có
        defaults = [
            ('daily_article_limit', '20',  'Giới hạn bài viết/ngày/user',  'number'),
            ('max_articles_per_gen', '5',  'Số bài tối đa/lần sinh',       'number'),
            ('maintenance_mode',    '0',   'Chế độ bảo trì (0=off, 1=on)', 'number'),
            ('site_name',  'AI E-Magazine','Tên trang web',                 'text'),
            ('contact_email', '',          'Email liên hệ admin',           'email'),
            ('payment_gateway', 'sepay',   'Cổng thanh toán mặc định',      'text'),
            ('payment_sepay_enabled', '1', 'Bật SePay',                     'number'),
            ('payment_vnpay_enabled', '0', 'Bật VNPAY',                     'number'),
        ]
        cursor.executemany("""
            INSERT IGNORE INTO system_settings (`key`, `value`, `label`, `type`)
            VALUES (%s, %s, %s, %s)
        """, defaults)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ init_settings_table: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Đọc / ghi settings
# ----------------------------------
def get_all_settings():
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM system_settings ORDER BY `key`")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ get_all_settings: {e}")
        if conn:
            conn.close()
        return []


def get_setting(key, default=None):
    conn = get_connection()
    if not conn:
        return default
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT `value` FROM system_settings WHERE `key` = %s", (key,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row['value'] if row else default
    except Exception as e:
        print(f"❌ get_setting: {e}")
        if conn:
            conn.close()
        return default


def set_setting(key, value):
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_settings (`key`, `value`) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE `value` = %s, updated_at = CURRENT_TIMESTAMP
        """, (key, value, value))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ set_setting: {e}")
        if conn:
            conn.close()
        return False


def save_settings_bulk(data: dict):
    """Lưu nhiều settings cùng lúc. data = {key: value, ...}"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        for k, v in data.items():
            cursor.execute("""
                INSERT INTO system_settings (`key`, `value`) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE `value` = %s, updated_at = CURRENT_TIMESTAMP
            """, (k, v, v))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ save_settings_bulk: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Error / Generation logs
# ----------------------------------
def get_generation_logs(status=None, limit=50, offset=0):
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        where = "WHERE gl.status = %s" if status else ""
        params = [status] if status else []
        params += [limit, offset]
        cursor.execute(f"""
            SELECT gl.*, u.email AS user_email, u.full_name AS user_name,
                   a.title AS article_title
            FROM generation_logs gl
            LEFT JOIN users u ON gl.user_id = u.id
            LEFT JOIN articles a ON gl.article_id = a.id
            {where}
            ORDER BY gl.created_at DESC
            LIMIT %s OFFSET %s
        """, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ get_generation_logs: {e}")
        if conn:
            conn.close()
        return []


def count_generation_logs(status=None):
    conn = get_connection()
    if not conn:
        return 0
    try:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT COUNT(*) FROM generation_logs WHERE status = %s", (status,))
        else:
            cursor.execute("SELECT COUNT(*) FROM generation_logs")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        print(f"❌ count_generation_logs: {e}")
        if conn:
            conn.close()
        return 0


def get_log_stats():
    """Thống kê generation_logs"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
              COUNT(*) AS total,
              SUM(status='success')    AS success,
              SUM(status='failed')     AS failed,
              SUM(status='processing') AS processing,
              ROUND(AVG(CASE WHEN generation_time > 0 THEN generation_time END), 1) AS avg_time
            FROM generation_logs
        """)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row or {}
    except Exception as e:
        print(f"❌ get_log_stats: {e}")
        if conn:
            conn.close()
        return {}


# ----------------------------------
# Schedules với magazine info
# ----------------------------------
def get_all_schedules_detail():
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, m.title AS magazine_title, m.topic AS magazine_topic,
                   u.email AS owner_email
            FROM magazine_schedules s
            LEFT JOIN magazines m ON s.magazine_id = m.id
            LEFT JOIN users u ON s.user_id = u.id
            ORDER BY s.created_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ get_all_schedules_detail: {e}")
        if conn:
            conn.close()
        return []


def admin_toggle_schedule_db(schedule_id):
    """Admin: toggle is_active của schedule bất kể user_id. Trả về new is_active hoặc None."""
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT is_active FROM magazine_schedules WHERE id = %s", (schedule_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close(); conn.close()
            return None
        new_state = 0 if row['is_active'] else 1
        cursor.execute("UPDATE magazine_schedules SET is_active = %s WHERE id = %s", (new_state, schedule_id))
        conn.commit()
        cursor.close(); conn.close()
        return new_state
    except Exception as e:
        print(f"❌ admin_toggle_schedule_db: {e}")
        if conn:
            conn.close()
        return None


def admin_delete_schedule_db(schedule_id):
    """Admin: xóa schedule bất kể user_id."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM magazine_schedules WHERE id = %s", (schedule_id,))
        conn.commit()
        ok = cursor.rowcount > 0
        cursor.close(); conn.close()
        return ok
    except Exception as e:
        print(f"❌ admin_delete_schedule_db: {e}")
        if conn:
            conn.close()
        return False
