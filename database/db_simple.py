"""
Database Connection & Configuration - Simplified Version with Connection Pool
"""
import mysql.connector
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool
import threading

# ----------------------------------
# Cấu hình MySQL
# ----------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ai_e_magazine_v2",
    "port": 3307,           # Port XAMPP của bạn
    "connect_timeout": 10,  # Tránh treo khi MySQL không phản hồi
}

# ----------------------------------
# Connection Pool (singleton, thread-safe)
# ----------------------------------
_pool: MySQLConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> MySQLConnectionPool | None:
    """Khởi tạo hoặc trả về connection pool hiện có (lazy init)."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            _pool = MySQLConnectionPool(
                pool_name="ai_magazine_pool",
                pool_size=10,
                pool_reset_session=True,
                **DB_CONFIG,
            )
            print("✅ Connection pool initialized (size=10)")
        except Error as e:
            print(f"⚠️  Cannot create connection pool: {e}")
            _pool = None
    return _pool


def reset_pool():
    """Reset pool (gọi sau khi init_database tạo xong database)."""
    global _pool
    with _pool_lock:
        _pool = None


# ----------------------------------
# Kết nối MySQL (từ pool hoặc fallback trực tiếp)
# ----------------------------------
def get_connection():
    """Lấy kết nối từ pool. Gọi conn.close() để trả lại pool (không đóng TCP)."""
    pool = _get_pool()
    if pool:
        try:
            return pool.get_connection()
        except Error as e:
            print(f"⚠️  Pool get_connection failed ({e}), falling back to direct")
    # Fallback: kết nối trực tiếp (dùng khi pool chưa sẵn sàng)
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"❌ Lỗi kết nối MySQL: {e}")
    return None


# ----------------------------------
# Khởi tạo Database
# ----------------------------------
def init_database():
    """Khởi tạo database từ file schema_simple.sql"""
    try:
        # Đọc file SQL
        with open('database/schema_simple.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Kết nối MySQL (không chọn database)
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"]
        )
        cursor = conn.cursor()
        
        # Thực thi các câu lệnh SQL
        statements = sql_script.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except Error as e:
                    if "already exists" not in str(e):
                        print(f"⚠️  Warning: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()

        # Reset pool để lần kết nối tiếp theo dùng database mới tạo
        reset_pool()
        
        print("✅ Database initialized successfully!")
        return True
        
    except FileNotFoundError:
        print("❌ File schema_simple.sql not found!")
        return False
    except Error as e:
        print(f"❌ Error initializing database: {e}")
        return False


# ----------------------------------
# Test Connection
# ----------------------------------
def database_exists() -> bool:
    """Kiểm tra database ai_e_magazine_v2 có tồn tại chưa (không phụ thuộc dữ liệu bên trong).
    Kết nối không chọn database, rồi truy vấn information_schema.
    Trả về False nếu không thể kết nối MySQL (khác với 'database chưa tạo').
    """
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
            connect_timeout=DB_CONFIG["connect_timeout"],
        )
        cursor = conn.cursor()
        cursor.execute(
            "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s",
            (DB_CONFIG["database"],),
        )
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return exists
    except Error:
        return False


def test_connection():
    """Test kết nối database"""
    conn = get_connection()
    if conn:
        print("✅ Database connection successful!")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        result = cursor.fetchone()
        count = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else 0
        print(f"📊 Total users: {count}")
        cursor.close()
        conn.close()
        return True
    else:
        print("❌ Database connection failed!")
        return False


# ----------------------------------
# Đảm bảo các indexes hiệu năng
# ----------------------------------
def ensure_performance_indexes():
    """Tạo composite indexes cần thiết cho hiệu năng truy vấn.
    Chỉ chạy một lần khi khởi động ứng dụng.
    """
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()

        indexes_to_create = [
            # index cho truy vấn bài liên quan: WHERE status=? AND topic=? AND id!=?
            (
                "articles",
                "idx_articles_status_topic",
                "ALTER TABLE articles ADD INDEX idx_articles_status_topic (status, topic)",
            ),
            # index cho truy vấn top views: WHERE status='published' ORDER BY view_count DESC
            (
                "articles",
                "idx_articles_status_views",
                "ALTER TABLE articles ADD INDEX idx_articles_status_views (status, view_count DESC)",
            ),
            # index cho user subscriptions lookup
            (
                "user_subscriptions",
                "idx_us_user_status",
                "ALTER TABLE user_subscriptions ADD INDEX idx_us_user_status (user_id, status)",
            ),
        ]

        for table, key_name, alter_sql in indexes_to_create:
            try:
                cursor.execute(
                    f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS "
                    f"WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s",
                    (table, key_name),
                )
                row = cursor.fetchone()
                if row and row[0] == 0:
                    cursor.execute(alter_sql)
                    conn.commit()
                    print(f"[OK] Added {key_name} on {table}")
            except Exception as e:
                # Một số ALTER TABLE syntax không hỗ trợ DESC index trên MySQL < 8
                # hoặc bảng chưa tồn tại — bỏ qua an toàn
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"[SKIP] {key_name}: {e}")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERR] ensure_performance_indexes: {e}")
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False


if __name__ == "__main__":
    print("🔧 Testing Database Connection...")
    test_connection()
