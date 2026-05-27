import sys
sys.path.insert(0, 'c:/xampp/htdocs/ai_e_magazine')
from database.db_simple import get_connection

conn = get_connection()
try:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT IFNULL(SUM(amount),0) AS v FROM payos_orders"
        " WHERE status='paid' AND DATE(created_at)=CURDATE()"
    )
    print('today:', cur.fetchone())
    cur.execute(
        "SELECT IFNULL(SUM(amount),0) AS v FROM payos_orders"
        " WHERE status='paid'"
        " AND YEAR(created_at)=YEAR(NOW()) AND MONTH(created_at)=MONTH(NOW())"
    )
    print('month:', cur.fetchone())
    cur.close()
except Exception as e:
    print('ERROR:', e)
finally:
    conn.close()
