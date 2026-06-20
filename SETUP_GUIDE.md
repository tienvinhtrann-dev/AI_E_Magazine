# 📖 AI E-Magazine — Hướng Dẫn Cài Đặt & Chạy Dự Án

> Dự án gồm 2 phần:
> - **Backend Web App** – Flask (Python) + MySQL (XAMPP)
> - **Mobile App** – Flutter (Android/iOS)

---

## 📋 Mục Lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cài đặt XAMPP & MySQL](#2-cài-đặt-xampp--mysql)
3. [Cài đặt Python & môi trường ảo](#3-cài-đặt-python--môi-trường-ảo)
4. [Cấu hình file `.env`](#4-cấu-hình-file-env)
5. [Khởi tạo Database](#5-khởi-tạo-database)
6. [Chạy Backend (Flask)](#6-chạy-backend-flask)
7. [Cài đặt & Build Flutter App](#7-cài-đặt--build-flutter-app)
8. [Cấu hình dịch vụ bên ngoài](#8-cấu-hình-dịch-vụ-bên-ngoài)
9. [Tài khoản mặc định](#9-tài-khoản-mặc-định)
10. [Xử lý sự cố thường gặp](#10-xử-lý-sự-cố-thường-gặp)

---

## 1. Yêu Cầu Hệ Thống

| Phần mềm | Phiên bản tối thiểu | Ghi chú |
|---|---|---|
| **Python** | 3.8+ | Khuyến nghị 3.10+ |
| **XAMPP** | 8.x | Bao gồm MySQL |
| **MySQL** | 5.7+ / 8.0+ | Chạy qua XAMPP |
| **Flutter SDK** | 3.x+ | Chỉ cần cho Mobile App |
| **Java JDK** | 17 | Chỉ cần cho Flutter/Android |
| **Android Studio** | Latest | Chỉ cần để build Android |
| **Git** | Bất kỳ | Để clone repo |

---

## 2. Cài Đặt XAMPP & MySQL

### 2.1 Tải & Cài XAMPP

1. Tải XAMPP tại: https://www.apachefriends.org/download.html
2. Cài đặt theo wizard (chọn **Apache** + **MySQL**)
3. Mở **XAMPP Control Panel** và khởi động **MySQL**

### 2.2 Kiểm tra port MySQL

Dự án này dùng **MySQL port 3307** (không phải 3306 mặc định).

Kiểm tra trong XAMPP Control Panel → MySQL → **Config** → `my.ini`:

```ini
[mysqld]
port = 3307
```

> ⚠️ Nếu bạn dùng port khác (ví dụ 3306), hãy sửa file `database/db_simple.py`:
> ```python
> DB_CONFIG = {
>     "port": 3306,   # ← đổi về port của bạn
>     ...
> }
> ```

### 2.3 Tạo Database User (tuỳ chọn)

Mặc định dự án dùng user `root` không có mật khẩu. Nếu MySQL của bạn có mật khẩu, sửa trong `database/db_simple.py`:

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your_password_here",  # ← điền mật khẩu
    "database": "ai_e_magazine_v2",
    "port": 3307,
}
```

---

## 3. Cài Đặt Python & Môi Trường Ảo

### 3.1 Tải Python

Tải tại: https://www.python.org/downloads/

Khi cài nhớ **tick vào "Add Python to PATH"**.

Kiểm tra:
```bash
python --version
# Python 3.10.x (hoặc cao hơn)
```

### 3.2 Tạo môi trường ảo

Mở terminal (PowerShell/CMD) tại thư mục dự án:

```bash
cd c:\xampp\htdocs\ai_e_magazine

# Tạo môi trường ảo
python -m venv .venv
```

### 3.3 Kích hoạt môi trường ảo

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```

> Khi thành công, terminal sẽ hiện prefix `(.venv)` ở đầu dòng lệnh.

### 3.4 Cài đặt các gói Python

```bash
pip install -r requirements_simple.txt
```

Danh sách các gói chính:
| Gói | Mục đích |
|---|---|
| `flask==3.0.0` | Web framework |
| `mysql-connector-python==8.2.0` | Kết nối MySQL |
| `python-dotenv==1.0.1` | Đọc file `.env` |
| `requests==2.31.0` | HTTP client |
| `beautifulsoup4==4.12.2` | Web scraping |
| `google-generativeai==0.3.2` | Gemini AI |
| `google-auth>=2.47.0` | Google OAuth |

---

## 4. Cấu Hình File `.env`

Copy file mẫu và điền thông tin thật:

```bash
copy .env.example .env
```

Nội dung đầy đủ của file `.env`:

```env
# ============================================================
# AI API Keys
# ============================================================

# Groq API Key (KHUYẾN NGHỊ - Miễn phí & Cực nhanh)
# Đăng ký tại: https://console.groq.com/keys
GROQ_API_KEY=your-groq-api-key-here

# Google Gemini API Key (Backup)
# Lấy miễn phí tại: https://makersuite.google.com/app/apikey
GEMINI_API_KEY=your-gemini-api-key-here

# ============================================================
# Google OAuth Login
# ============================================================
# Tạo OAuth Client tại: https://console.cloud.google.com/
# Authorized redirect URIs: http://127.0.0.1:5000/auth/google/callback
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/auth/google/callback

# ============================================================
# SePay - Thanh toán chuyển khoản
# ============================================================
# Đăng ký tại: https://sepay.vn
SEPAY_API_KEY=your-sepay-api-key
SEPAY_WEBHOOK_SECRET=tapchidientu
SEPAY_BANK_BIN=970422          # Mã BIN ngân hàng (MB=970422, BIDV=970418)
SEPAY_BANK_NAME=MB
SEPAY_ACCOUNT_NO=0000000000    # Số tài khoản nhận tiền
SEPAY_ACCOUNT_NAME=HO TEN CHU TK
SEPAY_QR_TEMPLATE=compact2

# ============================================================
# VNPay - Cổng thanh toán online
# ============================================================
# Đăng ký tại: https://sandbox.vnpayment.vn/
VNPAY_TMN_CODE=YOUR_TMN_CODE
VNPAY_HASH_SECRET=YOUR_HASH_SECRET
VNPAY_PAYMENT_URL=https://sandbox.vnpayment.vn/paymentv2/vpcpay.html
VNPAY_RETURN_URL=http://localhost:5000/payment/vnpay-return

# ============================================================
# Email (Quên mật khẩu)
# ============================================================
# Dùng Gmail App Password (không phải mật khẩu đăng nhập)
# Tạo App Password: https://myaccount.google.com/apppasswords
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail App Password (16 ký tự)
MAIL_FROM_NAME=AI E-Magazine
MAIL_FROM_EMAIL=your-email@gmail.com

# ============================================================
# URL Public của App
# ============================================================
# Local development:
APP_BASE_URL=http://localhost:5000
# Hoặc dùng ngrok để expose ra internet:
# APP_BASE_URL=https://your-subdomain.ngrok-free.app
```

---

## 5. Khởi Tạo & Quản Lý Database

### 5.1 Khởi tạo lần đầu tiên
Database sẽ được tự động khởi tạo khi chạy app lần đầu. Tuy nhiên bạn cũng có thể chạy thủ công:

```bash
# Đảm bảo đã kích hoạt .venv và MySQL đang chạy
python -c "from database.db_simple import init_database; init_database()"
```

Lệnh này sẽ:
- Tạo database `ai_e_magazine_v2`
- Tạo tất cả các bảng từ `database/schema_simple.sql`
- Tạo tài khoản admin mặc định

### 5.2 File cơ sở dữ liệu dự phòng (`database.sql`)
- Ở thư mục gốc của dự án, tệp `database.sql` lưu trữ toàn bộ cấu trúc bảng (schema) và dữ liệu bài viết, người dùng, bình luận hiện tại của dự án.
- Bạn có thể dùng tệp `database.sql` này để import trực tiếp qua phpMyAdmin hoặc chạy qua MySQL CLI để khôi phục nhanh CSDL khi cần.

### 5.3 Công cụ CLI quản lý CSDL (`manage_db.py`)
Dự án đã tích hợp công cụ quản lý cơ sở dữ liệu để bạn sao lưu, phục hồi và làm sạch (reset) dữ liệu nhanh chóng.

**Cách chạy:**
* **Cách 1 (Windows):** Nhấp đúp chuột vào file `manage_db.bat` ở thư mục gốc.
* **Cách 2 (Giao diện tương tác):**
  ```bash
  python manage_db.py
  ```
* **Cách 3 (Dòng lệnh nhanh):**
  - Sao lưu CSDL hiện tại: `python manage_db.py backup` (Sao lưu vào thư mục `database/backups/`)
  - Phục hồi CSDL: `python manage_db.py restore`
  - Xóa sạch và tạo lại CSDL từ đầu: `python manage_db.py reset`
  - Kiểm tra trạng thái: `python manage_db.py status`

---

## 6. Chạy Backend (Flask)

### Cách 1 – Script tự động (Khuyến nghị)

```bash
# Double-click file này trong Explorer, hoặc chạy trong terminal:
start_simple.bat
```

Script sẽ tự động:
1. Kiểm tra MySQL đang chạy
2. Kiểm tra / cài packages Python
3. Kiểm tra / khởi tạo database
4. Khởi động Flask server

### Cách 2 – Chạy thủ công

```bash
# 1. Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# 2. Chạy app
python app.py
```

### Kết quả thành công

```
======================================================================
  AI E-MAGAZINE - SIMPLIFIED VERSION
======================================================================

  Initializing...
  Database connected!
  URL: http://127.0.0.1:5000
======================================================================
 * Running on http://0.0.0.0:5000
```

Truy cập web tại: **http://127.0.0.1:5000**

---

## 7. Cài Đặt & Build Flutter App

### 7.1 Cài Java JDK 17

Tải tại: https://www.oracle.com/java/technologies/downloads/#java17

Kiểm tra:
```bash
java -version
# java version "17.x.x"
```

### 7.2 Cài Flutter SDK

1. Tải Flutter: https://docs.flutter.dev/get-started/install/windows
2. Giải nén vào `C:\flutter`
3. Thêm `C:\flutter\bin` vào **PATH** (System Environment Variables)
4. Kiểm tra:
   ```bash
   flutter doctor
   ```

### 7.3 Cài Android Studio

1. Tải tại: https://developer.android.com/studio
2. Mở Android Studio → **SDK Manager** → cài:
   - Android SDK Platform **33+**
   - Android SDK **Build-Tools**
   - Android SDK **Command-line Tools**
3. Chấp nhận licenses:
   ```bash
   flutter doctor --android-licenses
   # Nhập 'y' cho tất cả
   ```

### 7.4 Cấu hình URL Backend

Mở file `flutter_app/lib/config/app_config.dart` và đặt URL đúng:

| Trường hợp | URL cần dùng |
|---|---|
| Android Emulator | `http://10.0.2.2:5000` |
| Thiết bị thật (cùng WiFi) | `http://192.168.x.x:5000` |
| Ngrok (public) | `https://your-subdomain.ngrok-free.app` |

### 7.5 Build APK

```bash
cd c:\xampp\htdocs\ai_e_magazine\flutter_app

# Cài dependencies
flutter pub get

# Build APK debug (để test)
flutter build apk --debug

# Build APK release (để phân phối)
flutter build apk --release
```

APK output:
```
flutter_app\build\app\outputs\flutter-apk\app-release.apk
```

### 7.6 Cài APK lên điện thoại

**Qua USB:**
```bash
flutter devices     # Kiểm tra thiết bị kết nối
flutter install     # Cài trực tiếp
```

**Copy thủ công:** Copy file `app-release.apk` sang điện thoại và cài (cần bật "Cài từ nguồn không rõ").

---

## 8. Cấu Hình Dịch Vụ Bên Ngoài

### 8.1 Groq API (AI tạo nội dung) – Miễn phí

1. Đăng ký tại: https://console.groq.com/keys
2. Tạo API Key mới
3. Điền vào `.env`: `GROQ_API_KEY=gsk_...`

> 💡 Groq nhanh hơn Gemini ~10x, giới hạn 30 requests/phút, miễn phí hoàn toàn.

### 8.2 Google Gemini API (AI Backup) – Miễn phí

1. Vào: https://makersuite.google.com/app/apikey
2. Tạo API Key
3. Điền vào `.env`: `GEMINI_API_KEY=AIzaSy...`

### 8.3 Google OAuth (Đăng nhập Google)

1. Vào: https://console.cloud.google.com/
2. Tạo project mới (hoặc chọn project có sẵn)
3. **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth Client ID**
4. Application type: **Web application**
5. Thêm Authorized redirect URIs:
   - `http://127.0.0.1:5000/auth/google/callback`
   - `http://localhost:5000/auth/google/callback`
6. Copy **Client ID** và **Client Secret** vào `.env`

### 8.4 SePay (Thanh toán chuyển khoản)

1. Đăng ký tại: https://sepay.vn
2. Kết nối tài khoản ngân hàng
3. Lấy **API Key** và **Webhook Secret**
4. Điền các thông tin vào `.env`
5. Cấu hình Webhook URL trong SePay dashboard:
   ```
   https://your-domain.com/payment/sepay-webhook
   ```
   > ⚠️ SePay webhook cần URL public (dùng ngrok khi test local).

### 8.5 VNPay (Cổng thanh toán)

1. Đăng ký tại: https://sandbox.vnpayment.vn/
2. Lấy **TmnCode** và **HashSecret** từ tài khoản sandbox
3. Điền vào `.env`
4. Return URL phải accessible từ internet (dùng ngrok khi test local)

### 8.6 Ngrok (Expose localhost ra internet)

Cần thiết để nhận webhook từ SePay/VNPay khi test local.

```bash
# Cài ngrok: https://ngrok.com/download
# Tạo tài khoản miễn phí và lấy authtoken

ngrok config add-authtoken your-authtoken
ngrok http 5000
```

Copy URL ngrok (ví dụ: `https://abc123.ngrok-free.app`) vào `.env`:
```env
APP_BASE_URL=https://abc123.ngrok-free.app
VNPAY_RETURN_URL=https://abc123.ngrok-free.app/payment/vnpay-return
```

### 8.7 Gmail App Password (Gửi email)

1. Bật **2-Step Verification** trên tài khoản Gmail
2. Vào: https://myaccount.google.com/apppasswords
3. Tạo App Password cho "Mail" → "Windows Computer"
4. Copy 16 ký tự vào `.env`: `MAIL_PASSWORD=xxxx xxxx xxxx xxxx`

---

## 9. Tài Khoản Mặc Định

Sau khi khởi tạo database, hệ thống tạo sẵn tài khoản admin:

| Trường | Giá trị |
|---|---|
| **Email** | `admin@magazine.com` |
| **Mật khẩu** | `admin123` |
| **Quyền** | Administrator |

> 🔒 **Khuyến nghị:** Đổi mật khẩu admin ngay sau khi đăng nhập lần đầu (hoặc trước khi deploy lên production).

---

## 10. Xử Lý Sự Cố Thường Gặp

### ❌ Lỗi: `Can't connect to MySQL server on 'localhost' (port 3307)`

**Nguyên nhân:** MySQL chưa chạy hoặc sai port.

**Giải pháp:**
1. Mở XAMPP Control Panel → Start **MySQL**
2. Kiểm tra port thực tế trong `my.ini`
3. Sửa `DB_CONFIG["port"]` trong `database/db_simple.py`

---

### ❌ Lỗi: `Access denied for user 'root'@'localhost'`

**Nguyên nhân:** MySQL yêu cầu mật khẩu.

**Giải pháp:**
1. Sửa `DB_CONFIG["password"]` trong `database/db_simple.py`
2. Hoặc reset mật khẩu root MySQL trong XAMPP

---

### ❌ Lỗi: `ModuleNotFoundError: No module named 'flask'`

**Nguyên nhân:** Chưa kích hoạt môi trường ảo hoặc chưa cài packages.

**Giải pháp:**
```bash
.\.venv\Scripts\Activate.ps1
pip install -r requirements_simple.txt
```

---

### ❌ Lỗi: `UnicodeDecodeError` trên Windows

**Nguyên nhân:** Encoding UTF-8 trên Windows terminal.

**Giải pháp:** Đã được xử lý trong `app.py`. Đảm bảo chạy đúng file này.

---

### ❌ Google OAuth không hoạt động (`redirect_uri_mismatch`)

**Nguyên nhân:** Redirect URI trong Google Console không khớp.

**Giải pháp:**
- Vào Google Cloud Console → Credentials → OAuth Client
- Thêm đúng URI vào **Authorized redirect URIs**:
  - `http://127.0.0.1:5000/auth/google/callback`

---

### ❌ SePay webhook không nhận được

**Nguyên nhân:** URL trong `.env` không public.

**Giải pháp:**
```bash
# Chạy ngrok
ngrok http 5000

# Cập nhật .env với URL ngrok mới
APP_BASE_URL=https://xxxx.ngrok-free.app

# Cập nhật webhook URL trong SePay dashboard
```

---

### ❌ Flutter: `flutter doctor` báo lỗi Android SDK

**Giải pháp:**
```bash
# Chấp nhận licenses
flutter doctor --android-licenses

# Hoặc set Android SDK path thủ công
flutter config --android-sdk "C:\Users\<user>\AppData\Local\Android\Sdk"
```

---

## 📁 Cấu Trúc Dự Án

```
ai_e_magazine/
├── .env                    # Biến môi trường (KHÔNG commit git)
├── .env.example            # Mẫu cấu hình
├── app.py                  # Entry point Flask app
├── start_simple.bat        # Script khởi động nhanh (Windows)
├── requirements_simple.txt # Python dependencies
│
├── app/                    # Flask application package
│   ├── __init__.py         # App factory
│   ├── config.py           # Cấu hình app
│   ├── extensions.py       # Extensions (scheduler, etc.)
│   ├── routes/             # Các route handlers
│   │   ├── admin.py        # Quản trị viên
│   │   ├── api.py          # REST API (cho Flutter app)
│   │   ├── article.py      # Bài viết
│   │   ├── auth.py         # Đăng nhập/đăng ký
│   │   ├── dashboard.py    # Dashboard người dùng
│   │   ├── magazine.py     # Tạp chí
│   │   ├── payment.py      # Thanh toán (SePay, VNPay)
│   │   └── public.py       # Trang công khai
│   ├── services/           # Business logic
│   └── utils/              # Tiện ích
│
├── database/               # Models & schema
│   ├── db_simple.py        # Kết nối DB + connection pool
│   ├── schema_simple.sql   # Schema khởi tạo database
│   ├── user_model_simple.py
│   ├── magazine_model_simple.py
│   ├── article_model_simple.py
│   ├── plan_model.py       # Gói đăng ký
│   ├── sepay_model.py      # Giao dịch SePay
│   └── ...
│
├── static/                 # CSS, JS, images
├── templates/              # Jinja2 HTML templates
│
└── flutter_app/            # Mobile App (Flutter)
    ├── lib/
    │   ├── main.dart
    │   ├── config/app_config.dart  # URL backend
    │   ├── models/
    │   ├── services/api_service.dart
    │   ├── providers/
    │   └── screens/
    ├── pubspec.yaml
    └── FLUTTER_SETUP.md    # Hướng dẫn chi tiết Flutter
```

---

## 🔗 API Endpoints Chính (cho Flutter App)

| Method | Endpoint | Mô tả |
|---|---|---|
| `POST` | `/api/login` | Đăng nhập |
| `POST` | `/api/register` | Đăng ký |
| `POST` | `/api/logout` | Đăng xuất |
| `GET` | `/api/me` | Thông tin người dùng hiện tại |
| `GET` | `/api/magazines` | Danh sách tạp chí |
| `GET` | `/api/magazine/<id>` | Chi tiết tạp chí + bài viết |
| `GET` | `/api/article/<id>` | Chi tiết bài viết |
| `GET` | `/api/articles/trending` | Bài viết nổi bật |
| `GET` | `/api/search?q=...` | Tìm kiếm |

---

*Cập nhật lần cuối: 2026-06-16*
