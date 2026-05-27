"""
Payment routes: SePay token purchases, /plans pricing page.
"""
import re
from urllib.parse import quote_plus

from flask import session, flash, redirect, url_for, render_template, request, jsonify

from app import config
from database.sepay_model import (
    create_order, get_order_by_code, mark_order_paid, mark_order_cancelled,
    verify_via_api,
)
from database.plan_model import get_all_plans, get_active_subscription, get_plan_by_id
from database.user_model_simple import add_tokens, get_user_token_balance


# Token packages: key -> {name, amount (VND), tokens}
SEPAY_PLANS = {
    "basic":   {"name": "Basic",    "amount": 2000,  "tokens": 10},
    "khoidau": {"name": "Khởi đầu", "amount": 5000,  "tokens": 15},
    "coban":   {"name": "Cơ bản",   "amount": 10000, "tokens": 35},
}


def _extract_order_code_from_text(text):
    if not text:
        return None
    m = re.search(r"AIMAG(\d+)", str(text), flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    m2 = re.search(r"(\d{8,13})", str(text))
    return int(m2.group(1)) if m2 else None


def _to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace(",", "").replace(".", "")
        return int(float(value))
    except Exception:
        return default


def _build_vietqr_url(order):
    amount = int(order["amount"])
    content = order["transfer_content"]
    account_name = quote_plus(config.SEPAY_ACCOUNT_NAME)
    add_info = quote_plus(content)
    return (
        "https://img.vietqr.io/image/"
        f"{config.SEPAY_BANK_BIN}-{config.SEPAY_ACCOUNT_NO}-{config.SEPAY_QR_TEMPLATE}.png"
        f"?amount={amount}&addInfo={add_info}&accountName={account_name}"
    )


def register_routes(app):

    @app.route("/plans")
    def pricing_page():
        plans      = get_all_plans(active_only=True)
        active_sub = None
        if 'user_id' in session:
            active_sub = get_active_subscription(session['user_id'])
        return render_template(
            'plans.html',
            plans=plans, active_sub=active_sub,
            user_email=session.get('user_email'),
            user_role=session.get('user_role'),
        )

    @app.route("/payment/create", methods=["POST"])
    def payment_create():
        if 'user_id' not in session:
            return jsonify({"error": "Chưa đăng nhập"}), 401

        plan_key = request.form.get("plan_key", "").strip().lower()
        plan     = SEPAY_PLANS.get(plan_key)

        # Support dynamic plans created from admin panel (sent as plan_id)
        if not plan:
            plan_id_raw = request.form.get("plan_id", type=int)
            if plan_id_raw:
                db_plan = get_plan_by_id(plan_id_raw)
                if db_plan and db_plan.get('is_active'):
                    plan = {
                        "name":   db_plan["name"],
                        "amount": int(db_plan["price_monthly"]),
                        "tokens": int(db_plan["articles_per_day"]),
                    }

        if not plan:
            flash("Gói không hợp lệ.", "danger")
            return redirect(url_for("dashboard", tab="plans"))

        if not (config.SEPAY_BANK_BIN and config.SEPAY_ACCOUNT_NO and config.SEPAY_ACCOUNT_NAME):
            flash("Chưa cấu hình SePay. Vui lòng liên hệ admin.", "danger")
            return redirect(url_for("dashboard", tab="plans"))

        user_id    = session["user_id"]
        order_code = create_order(user_id, plan["name"], plan["amount"], plan["tokens"])
        if not order_code:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Không thể tạo đơn hàng."}), 500
            flash("Không thể tạo đơn hàng. Vui lòng thử lại.", "danger")
            return redirect(url_for("dashboard", tab="plans"))

        # AJAX request → trả JSON để hiển thị popup
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            order = get_order_by_code(order_code)
            qr_url = _build_vietqr_url(order)
            return jsonify({
                "ok": True,
                "order_code": order_code,
                "qr_url": qr_url,
                "amount": plan["amount"],
                "tokens": plan["tokens"],
                "plan_name": plan["name"],
                "transfer_content": order["transfer_content"],
                "bank_name": config.SEPAY_BANK_NAME,
                "account_name": config.SEPAY_ACCOUNT_NAME,
                "account_no": config.SEPAY_ACCOUNT_NO,
            })

        return redirect(url_for("payment_invoice", order_code=order_code))

    @app.route("/payment/invoice/<int:order_code>")
    def payment_invoice(order_code):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        order = get_order_by_code(order_code)
        if not order:
            flash("Không tìm thấy đơn hàng.", "danger")
            return redirect(url_for("dashboard", tab="plans"))
        if session.get("user_id") != order.get("user_id") and session.get("user_role") != "admin":
            flash("Bạn không có quyền xem đơn hàng này.", "danger")
            return redirect(url_for("dashboard", tab="plans"))

        qr_url = _build_vietqr_url(order)
        return render_template(
            "payment_sepay.html",
            order=order,
            qr_url=qr_url,
            bank_name=config.SEPAY_BANK_NAME,
            account_name=config.SEPAY_ACCOUNT_NAME,
            account_no=config.SEPAY_ACCOUNT_NO,
        )

    @app.route("/payment/status/<int:order_code>")
    def payment_status(order_code):
        order = get_order_by_code(order_code)
        if not order:
            return jsonify({"error": "not found"}), 404

        # Compare as int to avoid type mismatch (session stores int, DB may vary)
        session_uid = session.get("user_id")
        order_uid   = order.get("user_id")
        try:
            uid_match = (int(session_uid) == int(order_uid))
        except (TypeError, ValueError):
            uid_match = False

        if not uid_match and session.get("user_role") != "admin":
            return jsonify({"error": "forbidden"}), 403

        # If still pending and API key is configured, try live SePay API poll
        if order.get("status") == "pending" and config.SEPAY_API_KEY:
            found, txn_id = verify_via_api(order, config.SEPAY_API_KEY, config.SEPAY_ACCOUNT_NO)
            if found:
                updated = mark_order_paid(order_code, sepay_txn_id=txn_id)
                if updated:
                    add_tokens(order["user_id"], order["tokens"])
                    print(f"[SEPAY STATUS POLL] ✅ Order {order_code} paid via API poll - +{order['tokens']} tokens")
                return jsonify({"status": "paid"})

        status = order.get("status", "pending")
        resp   = {"status": status}
        if status == "paid":
            resp["tokens"] = order.get("tokens", 0)
        return jsonify(resp)

    @app.route("/payment/success")
    def payment_success():
        """Chi redirect den dashboard sau khi webhook da xu ly.
        Khong tu mark paid o day de tranh user truy cap URL thu cong lay token mien phi.
        """
        order_code = request.args.get("order_code", type=int)
        if not order_code:
            flash("Mã đơn hàng không hợp lệ.", "danger")
            return redirect(url_for("dashboard", tab="plans"))
        order = get_order_by_code(order_code)
        if not order:
            flash("Không tìm thấy đơn hàng.", "danger")
            return redirect(url_for("dashboard", tab="plans"))
        # Bao mat: chi chap nhan neu webhook da xu ly truoc
        if order["status"] == "paid":
            if "user_id" in session and session["user_id"] == order["user_id"]:
                session["token_balance"] = get_user_token_balance(order["user_id"])
        elif order["status"] == "pending":
            flash("Đơn hàng đang chờ xác nhận từ SePay.", "warning")
            return redirect(url_for("payment_invoice", order_code=order_code))
        else:
            flash("Đơn hàng bị huỷ hoặc hết hạn.", "warning")
        return redirect(url_for("dashboard", tab="plans"))

    @app.route("/payment/cancel")
    def payment_cancel():
        order_code = request.args.get("order_code", type=int)
        if order_code:
            mark_order_cancelled(order_code)
        flash("Bạn đã huỷ thanh toán.", "warning")
        return redirect(url_for("dashboard", tab="plans"))

    @app.route("/payment/verify/<int:order_code>", methods=["POST"])
    def payment_verify(order_code):
        """User bam 'Toi da chuyen khoan' - chu dong goi SePay API kiem tra giao dich."""
        if 'user_id' not in session:
            return jsonify({"error": "unauthorized"}), 401

        order = get_order_by_code(order_code)
        if not order:
            return jsonify({"ok": False, "reason": "order_not_found"}), 404
        if session.get("user_id") != order.get("user_id"):
            return jsonify({"error": "forbidden"}), 403
        if order.get("status") == "paid":
            return jsonify({"ok": True, "status": "paid"})
        if order.get("status") in ("cancelled", "expired"):
            return jsonify({"ok": False, "reason": "order_cancelled_or_expired"})

        if not config.SEPAY_API_KEY:
            return jsonify({"ok": False, "reason": "api_key_not_configured",
                            "message": "Chưa cấu hình SEPAY_API_KEY. Vui lòng chờ webhook tự động."})

        found, txn_id = verify_via_api(order, config.SEPAY_API_KEY, config.SEPAY_ACCOUNT_NO)
        if found:
            updated = mark_order_paid(order_code, sepay_txn_id=txn_id)
            if updated:
                add_tokens(order["user_id"], order["tokens"])
                print(f"[SEPAY VERIFY] ✅ Order {order_code} paid via API - +{order['tokens']} tokens")
                return jsonify({"ok": True, "status": "paid"})
            else:
                # Da duoc xu ly boi webhook truoc do
                return jsonify({"ok": True, "status": "paid"})
        else:
            print(f"[SEPAY VERIFY] Order {order_code} not found in SePay API yet")
            return jsonify({"ok": False, "status": "pending",
                            "message": "Chưa tìm thấy giao dịch. Vui lòng chờ thêm 1-2 phút."})

    @app.route("/payment/webhook", methods=["GET", "POST"])
    def payment_webhook():
        # SePay goi GET de xac minh URL khi cau hinh webhook
        if request.method == "GET":
            return jsonify({"ok": True, "message": "SePay webhook endpoint active"}), 200
        print(f"\n[SEPAY] ═══════════════════════════════════════════════")
        print(f"[SEPAY] Webhook received at {request.remote_addr}")
        print(f"[SEPAY] Headers: {dict(request.headers)}")
        
        if config.SEPAY_WEBHOOK_SECRET:
            auth_raw = request.headers.get("Authorization", "")
            # SePay gửi: "Apikey <token>" hoặc "Bearer <token>"
            for prefix in ("Apikey ", "APIKey ", "Bearer ", "Token "):
                auth_raw = auth_raw.replace(prefix, "")
            incoming_token = (
                request.headers.get("X-SePay-Token", "")
                or auth_raw.strip()
            )
            print(f"[SEPAY] Secret check: incoming='{incoming_token[:20] if incoming_token else '(empty)'}' vs config='{config.SEPAY_WEBHOOK_SECRET[:20]}...'")
            if incoming_token != config.SEPAY_WEBHOOK_SECRET:
                print(f"[SEPAY] ❌ Unauthorized webhook - auth header: '{request.headers.get('Authorization', '(none)')[:30]}'")
                return jsonify({"error": "unauthorized"}), 401

        payload = request.get_json(silent=True) or {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        print(f"[SEPAY] Payload: {payload}")
        print(f"[SEPAY] Data: {data}")

        # Chi xu ly giao dich tien vao
        transfer_type = str(
            data.get("transferType") or data.get("transfer_type") or "in"
        ).lower()
        if transfer_type not in ("in", "credit", "1"):
            print(f"[SEPAY] Skipping outgoing transaction: transferType={transfer_type}")
            return jsonify({"ok": True, "message": "skipped_outgoing"}), 200

        raw_content = (
            data.get("content")
            or data.get("description")
            or data.get("transferContent")
            or data.get("transaction_content")
            or ""
        )
        order_code = _extract_order_code_from_text(raw_content)
        paid_amount = _to_int(
            data.get("transferAmount")
            or data.get("amount_in")
            or data.get("amount")
            or data.get("value")
        )
        sepay_txn_id = str(
            data.get("id")
            or data.get("transactionId")
            or data.get("transaction_id")
            or data.get("reference")
            or ""
        )
        print(f"[SEPAY] Extracted: order_code={order_code}, amount={paid_amount}, txn_id={sepay_txn_id}")

        if not order_code:
            print(f"[SEPAY] ⚠️  No order code found in content: '{raw_content}'")
            return jsonify({"ok": False, "reason": "order_not_found_in_content"}), 200

        order = get_order_by_code(order_code)
        if not order:
            print(f"[SEPAY] ⚠️  Order {order_code} not found in DB")
            return jsonify({"ok": False, "reason": "order_not_exist"}), 200

        print(f"[SEPAY] Order found: {order}")
        
        if order.get("status") == "paid":
            print(f"[SEPAY] ℹ️  Order {order_code} already paid")
            return jsonify({"ok": True, "message": "already_paid"}), 200

        if paid_amount < int(order.get("amount") or 0):
            print(f"[SEPAY] ⚠️  Insufficient amount: {paid_amount} < {order.get('amount')}")
            return jsonify({"ok": False, "reason": "insufficient_amount"}), 200

        try:
            order = mark_order_paid(order_code, sepay_txn_id=sepay_txn_id)
        except Exception as e:
            print(f"[SEPAY] ❌ webhook mark paid error: {e}")
            return jsonify({"ok": False, "reason": "db_error"}), 500

        if order:
            add_tokens(order["user_id"], order["tokens"])
            print(f"[SEPAY] ✅ Order {order_code} paid - +{order['tokens']} tokens for user {order['user_id']}")
        print(f"[SEPAY] ═══════════════════════════════════════════════\n")
        return jsonify({"ok": True}), 200

    @app.route("/payment/webhook-test/<int:order_code>", methods=["POST"])
    def payment_webhook_test(order_code):
        """Test endpoint để mock SePay webhook - chỉ dùng khi testing local."""
        print(f"\n[SEPAY TEST] Mock webhook for order {order_code}")
        order = get_order_by_code(order_code)
        if not order:
            return jsonify({"error": "order not found"}), 404
        
        print(f"[SEPAY TEST] Order found: {order}")
        print(f"[SEPAY TEST] Status before: {order.get('status')}")
        
        try:
            result = mark_order_paid(order_code, sepay_txn_id=f"TEST_{order_code}")
            if result:
                add_tokens(order["user_id"], order["tokens"])
                print(f"[SEPAY TEST] ✅ Order {order_code} marked paid - +{order['tokens']} tokens for user {order['user_id']}")
                return jsonify({"ok": True, "message": f"Order {order_code} marked as paid"}), 200
            else:
                return jsonify({"ok": False, "message": "Order already paid or not found"}), 200
        except Exception as e:
            print(f"[SEPAY TEST] ❌ Error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500
