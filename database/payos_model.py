"""
PayOS Model – Quản lý đơn thanh toán token qua PayOS
"""
from database.db_simple import get_connection
import time
import random


# ─────────────────────────────────────────────
# KHỞI TẠO BẢNG
# ─────────────────────────────────────────────

def init_payos_table():
    """Tạo bảng payos_orders nếu chưa có."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payos_orders (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                order_code    BIGINT NOT NULL UNIQUE,   -- mã số gửi lên PayOS
                user_id       INT    NOT NULL,
                plan_name     VARCHAR(50),
                amount        INT    NOT NULL,          -- số tiền VNĐ
                tokens        INT    NOT NULL,          -- số token sẽ cộng
                status        ENUM('pending','paid','cancelled','expired')
                              DEFAULT 'pending',
                payos_id      VARCHAR(100),             -- paymentLinkId từ PayOS
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_user   (user_id),
                INDEX idx_status (status),
                INDEX idx_code   (order_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[PAYOS] init error: {e}")
        return False


# ─────────────────────────────────────────────
# TẠO ĐƠN HÀNG
# ─────────────────────────────────────────────

def generate_order_code():
    """Sinh order_code nguyên dương unique (dùng timestamp + random)."""
    return int(time.time() * 1000) % 9_000_000_000 + random.randint(1, 999)


def create_order(user_id, plan_name, amount, tokens):
    """Tạo record đơn hàng mới, trả về order_code."""
    conn = get_connection()
    if not conn:
        return None
    try:
        order_code = generate_order_code()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO payos_orders (order_code, user_id, plan_name, amount, tokens)
            VALUES (%s, %s, %s, %s, %s)
        """, (order_code, user_id, plan_name, amount, tokens))
        conn.commit()
        cur.close()
        conn.close()
        return order_code
    except Exception as e:
        print(f"[PAYOS] create_order error: {e}")
        return None


# ─────────────────────────────────────────────
# CẬP NHẬT TRẠNG THÁI
# ─────────────────────────────────────────────

def get_order_by_code(order_code):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM payos_orders WHERE order_code = %s", (order_code,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print(f"[PAYOS] get_order error: {e}")
        return None


def mark_order_paid(order_code, payos_id=None):
    """Đánh dấu đơn đã thanh toán, trả về dict order hoặc None nếu đã xử lý."""
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        # Chỉ update khi còn 'pending' – tránh cộng token 2 lần
        cur.execute("""
            UPDATE payos_orders
            SET status = 'paid', payos_id = %s
            WHERE order_code = %s AND status = 'pending'
        """, (payos_id, order_code))
        conn.commit()
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return None   # đã xử lý rồi
        cur.execute("SELECT * FROM payos_orders WHERE order_code = %s", (order_code,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print(f"[PAYOS] mark_paid error: {e}")
        return None


def mark_order_cancelled(order_code):
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE payos_orders SET status = 'cancelled'
            WHERE order_code = %s AND status = 'pending'
        """, (order_code,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[PAYOS] mark_cancelled error: {e}")
        return False
