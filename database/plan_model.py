"""
Plan / Subscription / Payment Model
Quản lý gói dịch vụ, đăng ký, thanh toán
"""
from database.db_simple import get_connection
from datetime import datetime, timedelta


# ─────────────────────────────────────────────
# KHỞI TẠO BẢNG
# ─────────────────────────────────────────────

def init_plans_tables():
    """Tạo 3 bảng: subscription_plans, user_subscriptions, payment_transactions"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()

        # ── 1. Gói dịch vụ ──────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                name             VARCHAR(50)  NOT NULL,      -- Free / Pro / Business
                price_monthly    DECIMAL(10,2) DEFAULT 0.00, -- VNĐ hoặc USD
                magazines_limit  INT DEFAULT 2,              -- Số tạp chí tối đa
                articles_per_day INT DEFAULT 3,              -- Bài/ngày
                auto_schedule    TINYINT(1) DEFAULT 0,       -- Hỗ trợ lịch tự động
                description      TEXT,
                badge_color      VARCHAR(20) DEFAULT '#6c757d',
                is_active        TINYINT(1) DEFAULT 1,
                sort_order       INT DEFAULT 0,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── 2. Đăng ký của người dùng ────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                user_id          INT NOT NULL,
                plan_id          INT NOT NULL,
                status           ENUM('active','pending','expired','cancelled') DEFAULT 'pending',
                start_date       DATE,
                end_date         DATE,
                payment_method   VARCHAR(50) DEFAULT 'manual',
                amount_paid      DECIMAL(10,2) DEFAULT 0.00,
                notes            TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (plan_id) REFERENCES subscription_plans(id) ON DELETE CASCADE,
                INDEX idx_user   (user_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ── 3. Giao dịch thanh toán ──────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payment_transactions (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                user_id         INT NOT NULL,
                plan_id         INT NOT NULL,
                subscription_id INT,
                amount          DECIMAL(10,2) NOT NULL,
                status          ENUM('pending','completed','failed','refunded') DEFAULT 'pending',
                payment_method  VARCHAR(50) DEFAULT 'manual',
                ref_code        VARCHAR(100),
                notes           TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (plan_id) REFERENCES subscription_plans(id) ON DELETE CASCADE,
                INDEX idx_user   (user_id),
                INDEX idx_status (status),
                INDEX idx_created(created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        conn.commit()
        cur.close()
        conn.close()

        # Seed data mặc định nếu chưa có gói nào
        _seed_default_plans()
        return True
    except Exception as e:
        print(f"[PLAN] init error: {e}")
        return False


def _seed_default_plans():
    """Thêm 3 gói mặc định nếu bảng trống"""
    conn = get_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM subscription_plans")
        (count,) = cur.fetchone()
        default_plans = [
            ("Basic", 2000, 0, 10, 0, "#16a34a",
             "Nhận 10 Token – Website tạp chí, Đăng bài tự động, Hỗ trợ cơ bản qua email", 1),
            ("Khởi đầu", 5000, 0, 15, 1, "#059669",
             "Nhận 15 Token – Website tạp chí, Đăng bài tự động, Hỗ trợ ưu tiên, tư vấn triển khai", 2),
            ("Cơ bản", 10000, 0, 35, 1, "#059669",
             "Nhận 35 Token – Lịch đăng linh hoạt & số lượng lớn, Hỗ trợ chuyên sâu & tích hợp mở rộng", 3),
        ]

        if count == 0:
            # Gói mặc định mới: Starter / Plus / Pro (khớp với trang chủ)
            plans = default_plans
            cur.executemany("""
                INSERT INTO subscription_plans
                    (name, price_monthly, magazines_limit, articles_per_day,
                     auto_schedule, badge_color, description, sort_order)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, plans)
            conn.commit()
            print("[PLAN] Default plans seeded (Starter/Plus/Pro).")
        else:
            # Nếu đã có 3 gói cũ Free/Pro/Business thì migrate sang Starter/Plus/Pro
            cur.execute("SELECT id, name FROM subscription_plans ORDER BY sort_order, id")
            rows = cur.fetchall()
            names = {r[1] for r in rows}
            if len(rows) == 3 and names == {"Free", "Pro", "Business"}:
                id_free = next(r[0] for r in rows if r[1] == "Free")
                id_pro_old = next(r[0] for r in rows if r[1] == "Pro")
                id_business = next(r[0] for r in rows if r[1] == "Business")

                updates = [
                    # Free -> Starter
                    ("Starter", 200000, 2, 5, 1, "#6c757d",
                     "Gói khởi đầu – 2 website, tối đa 5 bài viết cho mỗi tạp chí", 1, id_free),
                    # Pro -> Plus
                    ("Plus", 500000, 5, 10, 1, "#10b981",
                     "Gói Plus – tối đa 5 website, tối đa 10 bài viết cho mỗi tạp chí", 2, id_pro_old),
                    # Business -> Pro
                    ("Pro", 1000000, 12, 15, 1, "#059669",
                     "Gói Pro – tới 12 website, tối đa 15 bài viết cho mỗi tạp chí", 3, id_business),
                ]
                cur.executemany("""
                    UPDATE subscription_plans
                    SET name=%s, price_monthly=%s, magazines_limit=%s,
                        articles_per_day=%s, auto_schedule=%s,
                        badge_color=%s, description=%s, sort_order=%s
                    WHERE id=%s
                """, updates)
                conn.commit()
                print("[PLAN] Migrated legacy Free/Pro/Business to Starter/Plus/Pro.")

            # Đồng bộ thông tin chuẩn cho 3 gói mặc định nếu đã tồn tại sẵn.
            for name, price, mags, arts, auto_schedule, color, desc, sort_order in default_plans:
                cur.execute("""
                    UPDATE subscription_plans
                    SET price_monthly=%s,
                        magazines_limit=%s,
                        articles_per_day=%s,
                        auto_schedule=%s,
                        badge_color=%s,
                        description=%s,
                        sort_order=%s
                    WHERE name=%s
                """, (price, mags, arts, auto_schedule, color, desc, sort_order, name))
            conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[PLAN] seed error: {e}")


# ─────────────────────────────────────────────
# PLAN CRUD
# ─────────────────────────────────────────────

def get_all_plans(active_only=False):
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        sql = "SELECT * FROM subscription_plans"
        if active_only:
            sql += " WHERE is_active=1"
        sql += " ORDER BY sort_order, id"
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[PLAN] get_all error: {e}")
        return []


def get_plan_by_id(plan_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM subscription_plans WHERE id=%s", (plan_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print(f"[PLAN] get_by_id error: {e}")
        return None


def create_plan(name, price_monthly, magazines_limit, articles_per_day,
                auto_schedule, description='', badge_color='#6c757d', sort_order=0):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO subscription_plans
                (name, price_monthly, magazines_limit, articles_per_day,
                 auto_schedule, description, badge_color, sort_order)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (name, price_monthly, magazines_limit, articles_per_day,
              auto_schedule, description, badge_color, sort_order))
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return new_id
    except Exception as e:
        print(f"[PLAN] create error: {e}")
        return None


def update_plan(plan_id, name, price_monthly, magazines_limit, articles_per_day,
                auto_schedule, description='', badge_color='#6c757d', sort_order=0):
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE subscription_plans
            SET name=%s, price_monthly=%s, magazines_limit=%s,
                articles_per_day=%s, auto_schedule=%s,
                description=%s, badge_color=%s, sort_order=%s
            WHERE id=%s
        """, (name, price_monthly, magazines_limit, articles_per_day,
              auto_schedule, description, badge_color, sort_order, plan_id))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        print(f"[PLAN] update error: {e}")
        return False


def toggle_plan_active(plan_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("UPDATE subscription_plans SET is_active = NOT is_active WHERE id=%s", (plan_id,))
        conn.commit()
        cur.execute("SELECT is_active FROM subscription_plans WHERE id=%s", (plan_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"[PLAN] toggle error: {e}")
        return None


def delete_plan(plan_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM subscription_plans WHERE id=%s", (plan_id,))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        print(f"[PLAN] delete error: {e}")
        return False


# ─────────────────────────────────────────────
# SUBSCRIPTION CRUD
# ─────────────────────────────────────────────

def get_all_subscriptions(status=None, limit=50, offset=0):
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        where = "WHERE us.status=%s" if status else ""
        params = [status] if status else []
        params += [limit, offset]
        cur.execute(f"""
            SELECT us.*,
                   u.email, u.full_name,
                   sp.name  AS plan_name,
                   sp.price_monthly,
                   sp.badge_color
            FROM user_subscriptions us
            JOIN users u  ON u.id  = us.user_id
            JOIN subscription_plans sp ON sp.id = us.plan_id
            {where}
            ORDER BY us.created_at DESC
            LIMIT %s OFFSET %s
        """, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[PLAN] get_subs error: {e}")
        return []


def count_all_subscriptions(status=None):
    conn = get_connection()
    if not conn:
        return 0
    try:
        cur = conn.cursor()
        where = "WHERE status=%s" if status else ""
        params = (status,) if status else ()
        cur.execute(f"SELECT COUNT(*) FROM user_subscriptions {where}", params)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        return 0


def get_subscriptions_by_user(user_id):
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT us.*, sp.name AS plan_name, sp.price_monthly, sp.badge_color,
                   sp.magazines_limit, sp.articles_per_day, sp.auto_schedule
            FROM user_subscriptions us
            JOIN subscription_plans sp ON sp.id = us.plan_id
            WHERE us.user_id=%s
            ORDER BY us.created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[PLAN] get_subs_user error: {e}")
        return []


def get_active_subscription(user_id):
    """Trả về gói đang active của user, hoặc None"""
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT us.*, sp.name AS plan_name, sp.price_monthly, sp.badge_color,
                   sp.magazines_limit, sp.articles_per_day, sp.auto_schedule
            FROM user_subscriptions us
            JOIN subscription_plans sp ON sp.id = us.plan_id
            WHERE us.user_id=%s AND us.status='active'
              AND (us.end_date IS NULL OR us.end_date >= CURDATE())
            ORDER BY us.end_date DESC
            LIMIT 1
        """, (user_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print(f"[PLAN] get_active error: {e}")
        return None


def create_subscription(user_id, plan_id, months=1,
                        payment_method='manual', amount_paid=0, notes=''):
    conn = get_connection()
    if not conn:
        return None
    try:
        start = datetime.now().date()
        end   = (datetime.now() + timedelta(days=30 * months)).date()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_subscriptions
                (user_id, plan_id, status, start_date, end_date,
                 payment_method, amount_paid, notes)
            VALUES (%s,%s,'active',%s,%s,%s,%s,%s)
        """, (user_id, plan_id, start, end,
              payment_method, amount_paid, notes))
        conn.commit()
        sub_id = cur.lastrowid
        cur.close()
        conn.close()
        return sub_id
    except Exception as e:
        print(f"[PLAN] create_sub error: {e}")
        return None


def update_subscription_status(sub_id, status):
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE user_subscriptions SET status=%s WHERE id=%s
        """, (status, sub_id))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        return False


def renew_subscription(sub_id, months=1, amount_paid=0, notes=''):
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE user_subscriptions
            SET end_date   = DATE_ADD(GREATEST(end_date, CURDATE()), INTERVAL %s MONTH),
                status     = 'active',
                amount_paid = amount_paid + %s,
                notes       = CONCAT(IFNULL(notes,''), ' | Gia hạn: ', %s)
            WHERE id=%s
        """, (months, amount_paid, notes, sub_id))
        conn.commit()
        ok = cur.rowcount > 0
        cur.close()
        conn.close()
        return ok
    except Exception as e:
        print(f"[PLAN] renew error: {e}")
        return False


def get_subscription_by_id(sub_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT us.*, u.email, u.full_name,
                   sp.name AS plan_name, sp.price_monthly, sp.badge_color
            FROM user_subscriptions us
            JOIN users u  ON u.id  = us.user_id
            JOIN subscription_plans sp ON sp.id = us.plan_id
            WHERE us.id=%s
        """, (sub_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        return None


# ─────────────────────────────────────────────
# PAYMENT TRANSACTIONS
# ─────────────────────────────────────────────

def add_payment(user_id, plan_id, amount, subscription_id=None,
                payment_method='manual', ref_code='', notes='', status='completed'):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO payment_transactions
                (user_id, plan_id, subscription_id, amount, status, payment_method, ref_code, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (user_id, plan_id, subscription_id, amount,
              status, payment_method, ref_code, notes))
        conn.commit()
        pid = cur.lastrowid
        cur.close()
        conn.close()
        return pid
    except Exception as e:
        print(f"[PLAN] add_payment error: {e}")
        return None


def get_payments(limit=50, offset=0, status=None):
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        where = "WHERE pt.status=%s" if status else ""
        params = [status] if status else []
        params += [limit, offset]
        cur.execute(f"""
            SELECT pt.*, u.email, u.full_name, sp.name AS plan_name, sp.badge_color
            FROM payment_transactions pt
            JOIN users u  ON u.id  = pt.user_id
            JOIN subscription_plans sp ON sp.id = pt.plan_id
            {where}
            ORDER BY pt.created_at DESC
            LIMIT %s OFFSET %s
        """, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[PLAN] get_payments error: {e}")
        return []


# ─────────────────────────────────────────────
# REVENUE STATISTICS
# ─────────────────────────────────────────────

def get_revenue_stats():
    """Thống kê tổng quan doanh thu"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor(dictionary=True)

        # Tổng doanh thu
        cur.execute("SELECT IFNULL(SUM(amount),0) AS total FROM payment_transactions WHERE status='completed'")
        total_revenue = cur.fetchone()['total']

        # Doanh thu tháng này
        cur.execute("""
            SELECT IFNULL(SUM(amount),0) AS total
            FROM payment_transactions
            WHERE status='completed'
              AND YEAR(created_at)  = YEAR(NOW())
              AND MONTH(created_at) = MONTH(NOW())
        """)
        month_revenue = cur.fetchone()['total']

        # Tổng đăng ký active
        cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE status='active'")
        active_subs = cur.fetchone()['cnt']

        # Đăng ký chờ xác nhận
        cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE status='pending'")
        pending_subs = cur.fetchone()['cnt']

        # Doanh thu 12 tháng gần nhất
        cur.execute("""
            SELECT DATE_FORMAT(created_at,'%Y-%m') AS month,
                   IFNULL(SUM(amount),0)           AS revenue,
                   COUNT(*)                         AS transactions
            FROM payment_transactions
            WHERE status='completed'
              AND created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(created_at,'%Y-%m')
            ORDER BY month
        """)
        monthly = cur.fetchall()

        # Doanh thu theo gói
        cur.execute("""
            SELECT sp.name, sp.badge_color,
                   IFNULL(SUM(pt.amount),0) AS revenue,
                   COUNT(pt.id)              AS transactions
            FROM subscription_plans sp
            LEFT JOIN payment_transactions pt
                   ON pt.plan_id=sp.id AND pt.status='completed'
            GROUP BY sp.id, sp.name, sp.badge_color
            ORDER BY revenue DESC
        """)
        by_plan = cur.fetchall()

        # Số user theo từng gói (active)
        cur.execute("""
            SELECT sp.name, sp.badge_color,
                   COUNT(us.id) AS total_subs,
                   SUM(us.status='active') AS active_subs
            FROM subscription_plans sp
            LEFT JOIN user_subscriptions us ON us.plan_id=sp.id
            GROUP BY sp.id, sp.name, sp.badge_color
            ORDER BY sp.sort_order
        """)
        subs_by_plan = cur.fetchall()

        cur.close()
        conn.close()
        return {
            'total_revenue':  float(total_revenue),
            'month_revenue':  float(month_revenue),
            'active_subs':    active_subs,
            'pending_subs':   pending_subs,
            'monthly':        monthly,
            'by_plan':        by_plan,
            'subs_by_plan':   subs_by_plan,
        }
    except Exception as e:
        print(f"[PLAN] revenue_stats error: {e}")
        return {}
