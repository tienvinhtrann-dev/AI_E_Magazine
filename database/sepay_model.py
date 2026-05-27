"""
SePay model - quan ly don thanh toan token qua chuyen khoan.
"""
from database.db_simple import get_connection
import time
import random
import urllib.request
import json


def init_sepay_table():
    """Tao bang sepay_orders neu chua co."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sepay_orders (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                order_code       BIGINT NOT NULL UNIQUE,
                user_id          INT NOT NULL,
                plan_name        VARCHAR(50),
                amount           INT NOT NULL,
                tokens           INT NOT NULL,
                transfer_content VARCHAR(120) NOT NULL,
                status           ENUM('pending','paid','cancelled','expired')
                                 DEFAULT 'pending',
                sepay_txn_id     VARCHAR(100),
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_user (user_id),
                INDEX idx_status (status),
                INDEX idx_code (order_code),
                INDEX idx_transfer_content (transfer_content)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[SEPAY] init error: {e}")
        return False


def generate_order_code():
    return int(time.time() * 1000) % 9_000_000_000 + random.randint(1, 999)


def build_transfer_content(order_code):
    """Noi dung chuyen khoan de SePay doi soat."""
    return f"AIMAG{int(order_code)}"


def create_order(user_id, plan_name, amount, tokens):
    conn = get_connection()
    if not conn:
        return None
    try:
        order_code = generate_order_code()
        transfer_content = build_transfer_content(order_code)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sepay_orders (order_code, user_id, plan_name, amount, tokens, transfer_content)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (order_code, user_id, plan_name, amount, tokens, transfer_content))
        conn.commit()
        cur.close()
        conn.close()
        return order_code
    except Exception as e:
        print(f"[SEPAY] create_order error: {e}")
        return None


def get_order_by_code(order_code):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM sepay_orders WHERE order_code = %s", (order_code,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print(f"[SEPAY] get_order error: {e}")
        return None


def mark_order_paid(order_code, sepay_txn_id=None):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            UPDATE sepay_orders
            SET status = 'paid', sepay_txn_id = %s
            WHERE order_code = %s AND status = 'pending'
        """, (sepay_txn_id, order_code))
        conn.commit()
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return None
        cur.execute("SELECT * FROM sepay_orders WHERE order_code = %s", (order_code,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print(f"[SEPAY] mark_paid error: {e}")
        return None


def mark_order_cancelled(order_code):
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE sepay_orders SET status = 'cancelled'
            WHERE order_code = %s AND status = 'pending'
        """, (order_code,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[SEPAY] mark_cancelled error: {e}")
        return False


def verify_via_api(order, api_key, account_no):
    """
    Goi SePay API de tim giao dich khop voi don hang.
    Returns True neu tim thay giao dich hop le, False neu khong.
    API: GET https://my.sepay.vn/userapi/transactions/list
    Headers: Authorization: Bearer {api_key}
    """
    if not api_key:
        print("[SEPAY] verify_via_api: no api_key configured")
        return False, None

    transfer_content = str(order.get("transfer_content", ""))
    order_amount = int(order.get("amount", 0))

    url = (
        "https://my.sepay.vn/userapi/transactions/list"
        f"?account_number={account_no}&limit=20"
    )
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except Exception as e:
        print(f"[SEPAY] API call failed: {e}")
        return False, None

    transactions = data.get("transactions") or data.get("data") or []
    print(f"[SEPAY] API returned {len(transactions)} transactions for content={transfer_content}")

    for txn in transactions:
        content = str(txn.get("transaction_content") or txn.get("content") or txn.get("description") or "")
        amount = int(float(txn.get("amount_in") or txn.get("transferAmount") or txn.get("amount") or 0))
        direction = str(txn.get("transfer_type") or txn.get("transferType") or "in").lower()

        if direction not in ("in", "credit", "1"):
            continue
        if transfer_content.lower() not in content.lower():
            continue
        if amount < order_amount:
            print(f"[SEPAY] Found txn but amount {amount} < required {order_amount}")
            continue

        txn_id = str(txn.get("id") or txn.get("transaction_id") or "")
        print(f"[SEPAY] ✅ API match: content='{content}' amount={amount} txn_id={txn_id}")
        return True, txn_id

    return False, None


def get_pending_orders_for_polling(max_age_seconds=7200, min_age_seconds=15):
    """
    Lay danh sach don hang pending de background job kiem tra.
    - max_age_seconds: bo qua don qua cu (default 2 tieng)
    - min_age_seconds: bo qua don vua tao (cho ngan hang xu ly, default 15s)
    """
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT * FROM sepay_orders
            WHERE status = 'pending'
              AND created_at >= DATE_SUB(NOW(), INTERVAL %s SECOND)
              AND created_at <= DATE_SUB(NOW(), INTERVAL %s SECOND)
            ORDER BY created_at ASC
        """, (max_age_seconds, min_age_seconds))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[SEPAY] get_pending_orders error: {e}")
        return []
