"""
Feedback model: receive contact messages from homepage and expose admin listing.
"""
from database.db_simple import get_connection


TABLE_SQL = """
CREATE TABLE IF NOT EXISTS contact_feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL,
    subject VARCHAR(255) DEFAULT '',
    message TEXT NOT NULL,
    source_page VARCHAR(120) DEFAULT 'home',
    ip_address VARCHAR(45) DEFAULT NULL,
    user_agent VARCHAR(255) DEFAULT NULL,
    status ENUM('new','read') DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_feedback_created (created_at),
    INDEX idx_feedback_status (status),
    INDEX idx_feedback_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def ensure_feedback_table():
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(TABLE_SQL)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[FEEDBACK] ensure table error: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return False


def create_feedback(name, email, subject, message, source_page='home', ip_address=None, user_agent=None):
    if not ensure_feedback_table():
        return False
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO contact_feedback
                (name, email, subject, message, source_page, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (name, email, subject or '', message, source_page or 'home', ip_address, user_agent),
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[FEEDBACK] create error: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return False


def get_feedback_messages(limit=200):
    if not ensure_feedback_table():
        return []
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT id, name, email, subject, message, source_page, status, created_at
            FROM contact_feedback
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (int(limit),),
        )
        rows = cur.fetchall() or []
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[FEEDBACK] get list error: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return []


def get_feedback_stats():
    if not ensure_feedback_table():
        return {'total': 0, 'new': 0, 'today': 0}
    conn = get_connection()
    if not conn:
        return {'total': 0, 'new': 0, 'today': 0}
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) AS new_count,
                SUM(CASE WHEN DATE(created_at)=CURDATE() THEN 1 ELSE 0 END) AS today_count
            FROM contact_feedback
            """
        )
        row = cur.fetchone() or {}
        cur.close()
        conn.close()
        return {
            'total': int(row.get('total') or 0),
            'new': int(row.get('new_count') or 0),
            'today': int(row.get('today_count') or 0),
        }
    except Exception as e:
        print(f"[FEEDBACK] stats error: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return {'total': 0, 'new': 0, 'today': 0}
