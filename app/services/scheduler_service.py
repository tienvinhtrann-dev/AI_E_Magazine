"""
Scheduler service: scheduled article generation jobs.
"""
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.extensions import article_generator, scheduler
from database.magazine_model_simple import save_article_to_magazine
from database.schedule_model_simple import (
    get_all_active_schedules, update_schedule_last_run, get_schedule_by_id
)
from database.user_model_simple import get_user_token_balance, deduct_tokens
from app.utils.helpers import _refresh_magazine_category_counts


def _run_scheduled_generation(schedule_id, magazine_id, user_id, topic, keywords,
                               magazine_title, description, num_articles):
    """Run scheduled AI article generation - same logic as manual 'Tạo bài theo danh mục'."""
    print(f"[SCHED] Running schedule {schedule_id} for magazine {magazine_id}")
    try:
        # Kiểm tra số dư token trước khi chạy
        balance = get_user_token_balance(user_id)
        if balance is None or balance < num_articles:
            print(f"[SCHED] Skip schedule {schedule_id}: không đủ token ({balance} < {num_articles})")
            return

        # Lấy thông tin mới nhất từ DB (tránh dùng giá trị cũ trong kwargs)
        schedule_db = get_schedule_by_id(schedule_id)
        if schedule_db:
            topic    = (schedule_db.get('category_name') or topic or '').strip() or topic
            keywords = schedule_db.get('keywords') or keywords

        # Xây dựng description giống luồng thủ công ở dashboard
        cat_keywords = (keywords or '').strip() or topic
        extra        = f"; Từ khóa: {cat_keywords}" if cat_keywords else ''
        base_desc    = (description or '').strip()
        cat_description = (
            f"{base_desc} (Danh mục: {topic}{extra})" if base_desc
            else f"{topic}{extra}"
        )

        saved = 0
        for _ in range(num_articles):
            art = article_generator.generate_single_article_for_category(
                topic=topic,
                magazine_title=magazine_title,
                description=cat_description,
                keywords=cat_keywords,
            )
            if not art:
                continue
            aid = save_article_to_magazine(
                magazine_id=magazine_id,
                user_id=user_id,
                title=art.get('title'),
                content=art.get('content'),
                summary=art.get('summary'),
                keywords=art.get('keywords'),
                topic=art.get('topic') or topic,
                image_url=art.get('image_url', ''),
                image_urls=art.get('all_images') or art.get('image_urls'),
                source_urls=art.get('source_urls'),
            )
            if aid:
                saved += 1

        _refresh_magazine_category_counts(magazine_id)
        update_schedule_last_run(schedule_id)
        if saved > 0:
            deduct_tokens(user_id, saved)
        print(f"[SCHED] Done: {saved}/{num_articles} articles saved for magazine {magazine_id}, {saved} tokens deducted")
    except Exception as e:
        import traceback
        print(f"[SCHED] Error for schedule {schedule_id}: {e}")
        traceback.print_exc()


def _register_schedule_job(schedule):
    """Register a schedule into APScheduler."""
    sid = schedule['id']
    job_id = f"sched_{sid}"
    freq = schedule['frequency']
    hour = schedule['hour']
    minute = schedule['minute']
    interval_minutes = int(schedule.get('interval_minutes') or 0)
    days = schedule.get('days_of_week', '') or ''

    if freq == 'interval_min':
        trigger = IntervalTrigger(minutes=interval_minutes if interval_minutes > 0 else 5)
    elif freq == 'interval_hour':
        hours = (interval_minutes // 60) if interval_minutes >= 60 else 1
        trigger = IntervalTrigger(hours=hours)
    elif freq == 'daily':
        trigger = CronTrigger(hour=hour, minute=minute)
    elif freq == 'weekly':
        day_of_week = days if days else 'mon'
        trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
    else:  # custom
        trigger = CronTrigger(day_of_week=days if days else 'mon-fri', hour=hour, minute=minute)

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        func=_run_scheduled_generation,
        trigger=trigger,
        id=job_id,
        kwargs={
            'schedule_id': sid,
            'magazine_id': schedule['magazine_id'],
            'user_id': schedule['user_id'],
            'topic': schedule['topic'],
            'keywords': schedule['keywords'],
            'magazine_title': schedule['magazine_title'],
            'description': schedule.get('description', ''),
            'num_articles': schedule['num_articles'],
        },
        replace_existing=True,
        misfire_grace_time=3600
    )
    print(f"[SCHED] Job registered: {job_id}")


def _load_all_schedules():
    """Load all active schedules from DB into APScheduler at startup."""
    try:
        schedules = get_all_active_schedules()
        for s in schedules:
            _register_schedule_job(s)
        print(f"[SCHED] Loaded {len(schedules)} active schedule(s).")
    except Exception as e:
        print(f"[SCHED] Error loading schedules: {e}")


# ── SePay background payment polling ─────────────────────────────

def _poll_pending_sepay_orders():
    """
    Background job: kiem tra don hang sepay pending qua SePay API.
    Chay moi 20 giay. Neu don hang duoc xac nhan → mark paid + cong token.
    Yeu cau: SEPAY_API_KEY va SEPAY_ACCOUNT_NO trong .env.
    """
    import os
    api_key = os.getenv('SEPAY_API_KEY', '').strip()
    account_no = os.getenv('SEPAY_ACCOUNT_NO', '').strip()
    if not api_key or not account_no:
        return  # chua cau hinh API key, bo qua

    try:
        from database.sepay_model import get_pending_orders_for_polling, mark_order_paid, verify_via_api
        from database.user_model_simple import add_tokens

        orders = get_pending_orders_for_polling(max_age_seconds=7200, min_age_seconds=15)
        if not orders:
            return

        print(f"[SEPAY POLL] Checking {len(orders)} pending order(s)...")
        for order in orders:
            try:
                found, txn_id = verify_via_api(order, api_key, account_no)
                if found:
                    result = mark_order_paid(order['order_code'], sepay_txn_id=txn_id)
                    if result:
                        add_tokens(order['user_id'], order['tokens'])
                        print(
                            f"[SEPAY POLL] ✅ Order {order['order_code']} confirmed "
                            f"→ +{order['tokens']} tokens for user {order['user_id']}"
                        )
            except Exception as e:
                print(f"[SEPAY POLL] Error checking order {order.get('order_code')}: {e}")
    except Exception as e:
        print(f"[SEPAY POLL] Job error: {e}")


def start_sepay_poll_job():
    """Dang ky job poll SePay vao APScheduler (goi sau khi scheduler.start())."""
    import os
    api_key = os.getenv('SEPAY_API_KEY', '').strip()
    if not api_key:
        print("[SEPAY POLL] SEPAY_API_KEY chua duoc cau hinh → background polling disabled.")
        print("[SEPAY POLL] De bat: them SEPAY_API_KEY=<key> vao file .env roi restart Flask.")
        return

    scheduler.add_job(
        func=_poll_pending_sepay_orders,
        trigger=IntervalTrigger(seconds=60),
        id='sepay_poll',
        replace_existing=True,
        misfire_grace_time=60,
    )
    print("[SEPAY POLL] ✅ Background payment polling started (every 60s).")
