# Hướng dẫn Cấu hình SePay Webhook

## 1. Chuẩn bị Ngrok (để test local)

Bạn đã có ngrok URL: `.ngrok-free.dev`

Chạy ngrok để expose app local ra public:
```bash
ngrok http 5000
```

Ngrok sẽ cho bạn URL dạng: `https://abc-123-xyz.ngrok-free.dev`

Lưu URL này - bạn sẽ dùng cho webhook endpoint.

## 2. Cấu hình biến môi trường

Cập nhật file `.env`:

```env
# SePay Webhook Secret - sinh một chuỗi random dài để bảo mật
# Ví dụ: bạn có thể dùng: python -c "import secrets; print(secrets.token_hex(32))"
SEPAY_WEBHOOK_SECRET=your-random-secret-here

# Các thông tin tài khoản SePay
SEPAY_API_KEY=your-sepay-api-key
SEPAY_BANK_BIN=970418
SEPAY_BANK_NAME=BIDV
SEPAY_ACCOUNT_NO=7850743546
SEPAY_ACCOUNT_NAME=TRAN TIEN VINH
SEPAY_QR_TEMPLATE=compact2
```

## 3. Cấu hình Webhook trên SePay Dashboard

1. Đăng nhập vào https://dashboard.sepay.vn
2. Đi tới: **Settings → Webhooks**
3. Thêm webhook mới:
   - **URL**: `https://abc-123-xyz.ngrok-free.dev/payment/webhook`
   - **Events**: Chọn **Transaction** (giao dịch)
   - **Secret**: Nhập giá trị từ `SEPAY_WEBHOOK_SECRET` ở trên
4. Lưu cấu hình

## 4. Kiểm tra Kết nối Webhook

### Cách 1: Test thực tế (chuyển khoản nhỏ)

1. Tạo đơn hàng mới trong app
2. Quét QR hoặc chuyển khoản theo hướng dẫn
3. Xem logs của app (Flask console):
   - Nếu thấy `[SEPAY] ✅ Order 123 paid`, webhook đã hoạt động ✅
   - Nếu thấy `[SEPAY] ⚠️ No order code found`, nội dung CK không khớp

### Cách 2: Mock Webhook (không cần chuyển khoản)

Sử dụng endpoint test để giả lập webhook từ SePay:

```bash
# Lấy order_code từ URL khi tạo đơn
# VD: /payment/invoice/1234567890

# Test webhook:
curl -X POST http://127.0.0.1:5000/payment/webhook-test/1234567890
```

Hoặc từ terminal PowerShell:
```powershell
$order_code = 1234567890
Invoke-WebRequest -Uri "http://127.0.0.1:5000/payment/webhook-test/$order_code" -Method POST
```

Nếu bạn thấy:
```json
{"ok": true, "message": "Order 1234567890 marked as paid"}
```

→ Mock webhook thành công!

## 5. Debug - Xem Logs Chi tiết

Khi chạy app, bạn sẽ thấy logs chi tiết:

```
[SEPAY] ═══════════════════════════════════════════════
[SEPAY] Webhook received at 203.0.113.42
[SEPAY] Headers: {...}
[SEPAY] Secret check: incoming='abc123...' vs config='xyz789...'
[SEPAY] Payload: {...}
[SEPAY] Extracted: order_code=1234567890, amount=10000, txn_id=TXN_ABC123
[SEPAY] Order found: {'id': 1, 'order_code': 1234567890, ...}
[SEPAY] ✅ Order 1234567890 paid - +35 tokens for user 5
[SEPAY] ═══════════════════════════════════════════════
```

### Nếu gặp lỗi:

**❌ No order code found**
→ Nội dung chuyển khoản không có `AIMAG<order_code>`
→ Sửa: Gửi nội dung CK đúng định dạng, ví dụ: `AIMAG1234567890`

**❌ Insufficient amount**
→ Số tiền chuyển < số tiền trong đơn
→ Sửa: Chuyển đúng số tiền hiển thị trên trang thanh toán

**❌ Unauthorized webhook**
→ Secret không khớp
→ Sửa: Kiểm tra `SEPAY_WEBHOOK_SECRET` trong `.env` khớp với SePay Dashboard

**❌ Order not found**
→ `order_code` không tồn tại trong DB
→ Kiểm tra: Đơn hàng có được tạo thành công không?

## 6. Kiểm tra Status Đơn Hàng

Sau khi chuyển khoản, bạn có thể check status:

```bash
curl http://127.0.0.1:5000/payment/status/1234567890
```

Response:
```json
{"status": "paid"}  // ✅ đã thanh toán
{"status": "pending"}  // ⏳ chờ webhook
```

## 7. Troubleshooting Ngrok

Nếu ngrok bị disconnect:
1. Chạy lại: `ngrok http 5000`
2. Copy URL ngrok mới
3. Update webhook URL trên SePay Dashboard

## 8. Production

Khi deploy production:
1. Thay `https://abc-123-xyz.ngrok-free.dev` bằng domain thật (vd: `https://yourdomain.com`)
2. Cập nhật webhook URL trên SePay Dashboard
3. Tạo `SEPAY_WEBHOOK_SECRET` mạnh hơn
4. Set `APP_BASE_URL` trong `.env` là domain public

---

**Liên hệ SePay Support nếu webhook vẫn không hoạt động:**
- Website: https://sepay.vn
- Docs: https://sepay.vn/docs
