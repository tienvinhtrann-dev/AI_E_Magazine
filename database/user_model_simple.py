"""
User Model - With Admin/User Roles
"""
from database.db_simple import get_connection
from werkzeug.security import generate_password_hash, check_password_hash
import secrets


# ----------------------------------
# Tạo User Mới
# ----------------------------------
def create_user(email, password, role='user', full_name=None, auth_provider='local', google_id=None):
    """
    Tạo user mới
    
    Args:
        email: Email người dùng
        password: Mật khẩu
        role: 'user' hoặc 'admin'
        full_name: Tên đầy đủ (optional)
    
    Returns:
        user_id nếu thành công, None nếu thất bại
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        hashed_password = generate_password_hash(password)
        
        query = """
        INSERT INTO users (email, password, role, full_name, auth_provider, google_id, token_balance) 
        VALUES (%s, %s, %s, %s, %s, %s, 5)
        """
        cursor.execute(query, (email, hashed_password, role, full_name, auth_provider, google_id))
        conn.commit()
        
        user_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        print(f"✅ User created: {email} (role: {role})")
        return user_id
        
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        if conn:
            conn.close()
        return None


# ----------------------------------
# Lấy User theo email
# ----------------------------------
def get_user_by_email(email):
    """Lấy thông tin user theo email."""
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM users WHERE email = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except Exception as e:
        print(f"❌ Error getting user by email: {e}")
        if conn:
            conn.close()
        return None


# ----------------------------------
# Đồng bộ tài khoản Google
# ----------------------------------
def sync_google_user(email, full_name=None, google_id=None):
    """Tạo hoặc cập nhật user đăng nhập bằng Google."""
    if not email:
        return None

    existing_user = get_user_by_email(email)
    if existing_user:
        conn = get_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET auth_provider = %s,
                    google_id = %s,
                    full_name = COALESCE(NULLIF(%s, ''), full_name)
                WHERE email = %s
                """,
                ('google', google_id, full_name, email),
            )
            conn.commit()
            cursor.close()
            conn.close()

            existing_user['auth_provider'] = 'google'
            existing_user['google_id'] = google_id
            if full_name:
                existing_user['full_name'] = full_name
            return existing_user
        except Exception as e:
            print(f"❌ Error syncing Google user: {e}")
            if conn:
                conn.close()
            return None

    temp_password = secrets.token_urlsafe(32)
    user_id = create_user(
        email=email,
        password=temp_password,
        role='user',
        full_name=full_name,
        auth_provider='google',
        google_id=google_id,
    )
    if not user_id:
        return None

    return get_user_by_email(email)


# ----------------------------------
# Đảm bảo schema hỗ trợ Google login
# ----------------------------------
def ensure_google_auth_schema():
    """Thêm cột auth_provider/google_id nếu database cũ chưa có."""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("SHOW COLUMNS FROM users LIKE 'auth_provider'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(20) DEFAULT 'local' AFTER full_name")

        cursor.execute("SHOW COLUMNS FROM users LIKE 'google_id'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN google_id VARCHAR(255) DEFAULT NULL AFTER auth_provider")

        cursor.execute("UPDATE users SET auth_provider = 'local' WHERE auth_provider IS NULL OR auth_provider = ''")
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error ensuring Google auth schema: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Đảm bảo schema có cột token_balance
# ----------------------------------
def ensure_token_balance_schema():
    """Thêm các cột còn thiếu vào bảng users (token_balance, is_active, magazine_limit, role premium)."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()

        cursor.execute("SHOW COLUMNS FROM users LIKE 'token_balance'")
        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE users ADD COLUMN token_balance INT NOT NULL DEFAULT 5 AFTER google_id"
            )

        cursor.execute("SHOW COLUMNS FROM users LIKE 'is_active'")
        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER token_balance"
            )
            print("[OK] Added is_active column to users")

        cursor.execute("SHOW COLUMNS FROM users LIKE 'magazine_limit'")
        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE users ADD COLUMN magazine_limit INT DEFAULT NULL AFTER is_active"
            )
            print("[OK] Added magazine_limit column to users")

        # Ensure role ENUM includes 'premium'
        cursor.execute("SHOW COLUMNS FROM users LIKE 'role'")
        role_row = cursor.fetchone()
        if role_row and 'premium' not in str(role_row):
            cursor.execute(
                "ALTER TABLE users MODIFY COLUMN role ENUM('user','admin','premium') DEFAULT 'user'"
            )
            print("[OK] Updated role ENUM to include premium")

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error ensuring token_balance schema: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Lấy số token của user
# ----------------------------------
def get_user_token_balance(user_id):
    """Trả về số token hiện tại của user. Mặc định 5 nếu lỗi."""
    conn = get_connection()
    if not conn:
        return 5
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT token_balance FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return int(row[0])
        return 5
    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return 5


# ----------------------------------
# Cộng token cho user (sau thanh toán)
# ----------------------------------
def add_tokens(user_id, amount):
    """Cộng thêm `amount` token vào tài khoản user. Trả về số dư mới."""
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET token_balance = token_balance + %s WHERE id = %s",
            (amount, user_id)
        )
        conn.commit()
        cursor.execute("SELECT token_balance FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return int(row[0]) if row else None
    except Exception as e:
        print(f"[TOKEN] add_tokens error: {e}")
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return None


# ----------------------------------
# Trừ token (atomic – trả None nếu không đủ)
# ----------------------------------
def deduct_tokens(user_id, amount):
    """Trừ `amount` token từ tài khoản user (atomic).
    Trả về số dư mới nếu thành công, None nếu không đủ token.
    """
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET token_balance = token_balance - %s WHERE id = %s AND token_balance >= %s",
            (amount, user_id, amount)
        )
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return None  # Không đủ token
        cursor.execute("SELECT token_balance FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return int(row[0]) if row else None
    except Exception as e:
        print(f"[TOKEN] deduct_tokens error: {e}")
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return None


# ----------------------------------
# Xác thực User
# ----------------------------------
def verify_user(email, password):
    """
    Xác thực user khi đăng nhập
    
    Returns:
        dict user info nếu thành công, None nếu thất bại
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM users WHERE email = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            if user.get('is_active', 1) == 0:
                return {'error': 'locked'}
            return {
                'id': user['id'],
                'email': user['email'],
                'role': user['role'],
                'full_name': user['full_name']
            }
        
        return None
        
    except Exception as e:
        print(f"❌ Error verifying user: {e}")
        if conn:
            conn.close()
        return None


# ----------------------------------
# Lấy User Info
# ----------------------------------
def get_user_by_id(user_id):
    """Lấy thông tin user theo ID"""
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, email, role, full_name, created_at FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        return user
        
    except Exception as e:
        print(f"❌ Error getting user: {e}")
        if conn:
            conn.close()
        return None


# ----------------------------------
# Kiểm tra User là Admin
# ----------------------------------
def is_admin(user_id):
    """Kiểm tra user có phải admin không"""
    user = get_user_by_id(user_id)
    return user and user['role'] == 'admin'


# ----------------------------------
# Lấy tất cả Users (Admin only)
# ----------------------------------
def get_all_users():
    """Lấy danh sách tất cả users (cho admin)"""
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT id, email, role, full_name, created_at 
        FROM users 
        ORDER BY created_at DESC
        """
        cursor.execute(query)
        users = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return users
        
    except Exception as e:
        print(f"❌ Error getting all users: {e}")
        if conn:
            conn.close()
        return []


# ----------------------------------
# Cập nhật Role User (Admin only)
# ----------------------------------
def update_user_role(user_id, new_role):
    """Cập nhật role của user (admin only)"""
    if new_role not in ['user', 'premium', 'admin']:
        return False
        
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        query = "UPDATE users SET role = %s WHERE id = %s"
        cursor.execute(query, (new_role, user_id))
        conn.commit()
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error updating user role: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Xóa User theo ID (Admin only)
# ----------------------------------
def delete_user_by_id(user_id):
    """Xóa user theo ID (admin only)"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        query = "DELETE FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error deleting user: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Lấy Users với stats (Admin only)
# ----------------------------------
def get_users_with_stats():
    """Lấy danh sách users kèm số lượng tạp chí và bài viết"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.magazine_limit,
               COALESCE(u.token_balance, 0) AS token_balance,
               COALESCE(u.auth_provider, 'local') AS auth_provider,
               u.created_at,
               COUNT(DISTINCT m.id) AS magazine_count,
               COUNT(DISTINCT a.id) AS article_count
        FROM users u
        LEFT JOIN magazines m ON m.user_id = u.id
        LEFT JOIN articles a ON a.user_id = u.id
        GROUP BY u.id
        ORDER BY u.created_at DESC
        """
        cursor.execute(query)
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return users
    except Exception as e:
        print(f"❌ Error get_users_with_stats: {e}")
        if conn:
            conn.close()
        return []


# ----------------------------------
# Cập nhật tên hiển thị (full_name)
# ----------------------------------
def update_user_display_name(user_id, display_name):
    """Cập nhật tên hiển thị (full_name) cho user."""
    if not user_id:
        return False

    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        query = "UPDATE users SET full_name = %s WHERE id = %s"
        cursor.execute(query, (display_name, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error updating display name: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Toggle khóa/mở tài khoản
# ----------------------------------
def toggle_user_active(user_id):
    """Đảo trạng thái is_active của user. Trả về trạng thái mới (0 hoặc 1)"""
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT is_active FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close(); conn.close()
            return None
        new_state = 0 if row['is_active'] else 1
        cursor.execute("UPDATE users SET is_active = %s WHERE id = %s", (new_state, user_id))
        conn.commit()
        cursor.close(); conn.close()
        return new_state
    except Exception as e:
        print(f"\u274c Error toggle_user_active: {e}")
        if conn:
            conn.close()
        return None


# ----------------------------------
# Cập nhật magazine_limit
# ----------------------------------
def set_magazine_limit(user_id, limit):
    """Đặt giới hạn số tạp chí cho user"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET magazine_limit = %s WHERE id = %s", (int(limit), user_id))
        conn.commit()
        cursor.close(); conn.close()
        return True
    except Exception as e:
        print(f"\u274c Error set_magazine_limit: {e}")
        if conn:
            conn.close()
        return False


# ----------------------------------
# Lịch sử hoạt động của User
# ----------------------------------
def get_user_activity(user_id, limit=20):
    """Trả về các bài viết/tạp chí gần đây của user"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT 'article' AS type, a.id, a.title, a.created_at, m.title AS magazine_title
        FROM articles a
        LEFT JOIN magazines m ON m.id = a.magazine_id
        WHERE a.user_id = %s
        UNION ALL
        SELECT 'magazine' AS type, m.id, m.title, m.created_at, NULL AS magazine_title
        FROM magazines m
        WHERE m.user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """
        cursor.execute(query, (user_id, user_id, limit))
        rows = cursor.fetchall()
        cursor.close(); conn.close()
        return rows
    except Exception as e:
        print(f"\u274c Error get_user_activity: {e}")
        if conn:
            conn.close()
        return []


# ----------------------------------
# Test Functions
# ----------------------------------
if __name__ == "__main__":
    print("🧪 Testing User Model...")
    
    # Test create user
    user_id = create_user("test@example.com", "test123", "user", "Test User")
    if user_id:
        print(f"✅ Created user with ID: {user_id}")
        
        # Test verify
        user = verify_user("test@example.com", "test123")
        if user:
            print(f"✅ Login successful: {user}")
        
        # Test is_admin
        print(f"Is admin? {is_admin(user_id)}")
