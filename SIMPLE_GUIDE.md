# 📰 AI E-MAGAZINE - Hướng Dẫn Cài Đặt và Sử Dụng

## 🎯 Giới thiệu

**AI E-Magazine** là hệ thống tạo báo điện tử tự động với AI. Hệ thống cho phép:

- 👤 Đăng ký / Đăng nhập người dùng
- ✍️ Tạo bài báo tự động từ từ khóa
- 🌐 Tự động crawl tin từ các trang tin tức
- 🤖 AI tổng hợp và viết lại thành bài báo mới
- 📰 Xuất bản và quản lý bài viết
- 👮 Phân quyền Admin/User

---

## 🚀 Cài Đặt

### **Bước 1: Chuẩn bị**

1. **Cài đặt Python 3.8+**
   - Tải tại: https://www.python.org/downloads/
   - Đánh dấu "Add Python to PATH"

2. **Cài đặt XAMPP**
   - Tải tại: https://www.apachefriends.org/
   - Khởi động MySQL trong XAMPP Control Panel

### **Bước 2: Setup Database**

1. Mở XAMPP Control Panel và Start **MySQL**

2. Truy cập phpMyAdmin: http://localhost/phpmyadmin

3. Import database:
   - Chọn tab "Import"
   - Upload file `database/schema_simple.sql`
   - Click "Go"

**HOẶC** chạy lệnh Python:
```bash
cd c:\xampp\htdocs\ai_e_magazine
python
>>> from database.db_simple import init_database
>>> init_database()
>>> exit()
```

### **Bước 3: Cài đặt Python Packages**

```bash
cd c:\xampp\htdocs\ai_e_magazine
pip install -r requirements_simple.txt
```

### **Bước 4: Chạy ứng dụng**

```bash
python app_simple.py
```

Truy cập: **http://127.0.0.1:5000**

---

## 📖 Hướng Dẫn Sử Dụng

### **1. Đăng ký tài khoản**

1. Truy cập: http://127.0.0.1:5000/register
2. Nhập email, mật khẩu, họ tên
3. Click "Đăng ký"

### **2. Đăng nhập**

1. Truy cập: http://127.0.0.1:5000/login
2. Nhập email và mật khẩu
3. Click "Đăng nhập"

**Tài khoản Admin mặc định:**
- Email: `admin@magazine.com`
- Password: `admin123`

### **3. Tạo bài báo tự động**

1. Click "✍️ Tạo bài mới"
2. Nhập:
   - **Chủ đề**: VD: "Trí Tuệ Nhân Tạo"
   - **Mô tả**: VD: "Tìm hiểu về AI trong đời sống"
   - **Từ khóa**: VD: "trí tuệ nhân tạo, ChatGPT"
3. Click "🚀 Tạo bài báo"
4. Đợi AI crawl và tạo bài (30-60 giây)
5. Hệ thống tự động chuyển đến trang chỉnh sửa

### **4. Chỉnh sửa và Xuất bản**

1. Sau khi AI tạo xong, bạn có thể:
   - Chỉnh sửa tiêu đề, nội dung
   - Xem trước
   - Lưu thay đổi
2. Click "📢 Xuất bản" để đăng bài
3. Bài viết sẽ xuất hiện trên trang chủ

### **5. Quản lý bài viết**

- **Dashboard**: Xem thống kê bài viết của bạn
- **Bài viết của tôi**: Xem tất cả bài viết (lọc theo trạng thái)
- **Xem/Sửa/Xóa**: Quản lý từng bài viết

### **6. Tính năng Admin**

Admin có thể:
- Xem tất cả bài viết
- Xem danh sách người dùng
- Xóa bất kỳ bài viết nào
- Quản lý hệ thống

Truy cập: http://127.0.0.1:5000/admin

---

## 🔧 Cấu trúc Dự án

```
ai_e_magazine/
├── app_simple.py              # Flask app chính
├── requirements_simple.txt     # Python dependencies
│
├── ai/
│   └── article_generator.py   # AI Generator
│
├── database/
│   ├── db_simple.py           # Database connection
│   ├── schema_simple.sql      # Database schema
│   ├── user_model_simple.py   # User CRUD
│   └── article_model_simple.py # Article CRUD
│
└── templates/                 # HTML templates
    ├── base.html
    ├── home.html
    ├── login.html
    ├── register.html
    ├── create_article.html
    ├── generate_progress.html
    ├── article_detail.html
    ├── edit_article.html
    ├── dashboard.html
    ├── my_articles.html
    ├── search_results.html
    └── admin_panel.html
```

---

## 🗄️ Database Schema

### **Bảng: users**
```sql
- id (PK)
- email (unique)
- password (hashed)
- role (user/admin)
- full_name
- created_at
```

### **Bảng: articles**
```sql
- id (PK)
- user_id (FK)
- title
- content
- summary
- keywords
- topic
- description
- status (draft/published/pending)
- source_urls (JSON)
- view_count
- created_at
- updated_at
- published_at
```

### **Bảng: article_history**
```sql
- id (PK)
- article_id (FK)
- user_id (FK)
- action (created/edited/published)
- old_content
- new_content
- created_at
```

### **Bảng: generation_logs**
```sql
- id (PK)
- user_id (FK)
- article_id (FK)
- topic
- keywords
- sources_crawled
- articles_found
- generation_time
- status
- error_message
- created_at
```

---

## 🎨 API Endpoints

### **Public**
- `GET /` - Trang chủ
- `GET /article/<id>` - Chi tiết bài viết
- `GET /search?q=<keyword>` - Tìm kiếm

### **Authentication**
- `GET/POST /register` - Đăng ký
- `GET/POST /login` - Đăng nhập
- `GET /logout` - Đăng xuất

### **User Dashboard**
- `GET /dashboard` - Dashboard
- `GET /my-articles` - Quản lý bài viết
- `GET/POST /create` - Tạo bài mới
- `GET /generate` - Trang progress
- `POST /api/generate` - API tạo bài
- `GET/POST /edit/<id>` - Chỉnh sửa
- `POST /publish/<id>` - Xuất bản
- `POST /delete/<id>` - Xóa

### **Admin**
- `GET /admin` - Admin panel

---

## ❓ Troubleshooting

### **Lỗi: Can't connect to MySQL server**
✅ **Giải pháp:**
- Mở XAMPP Control Panel
- Start MySQL
- Kiểm tra port trong `database/db_simple.py` (mặc định: 3306)

### **Lỗi: Access denied for user 'root'**
✅ **Giải pháp:**
- Kiểm tra password MySQL
- Cập nhật trong `database/db_simple.py`:
  ```python
  "password": "your_password_here"
  ```

### **Lỗi: No module named 'flask'**
✅ **Giải pháp:**
```bash
pip install -r requirements_simple.txt
```

### **Lỗi: Không crawl được bài viết**
✅ **Giải pháp:**
- Thử từ khóa khác (bằng tiếng Việt)
- Kiểm tra kết nối internet
- VnExpress là nguồn ổn định nhất

### **Bài viết quá ngắn**
✅ **Giải pháp:**
- Thay đổi từ khóa cụ thể hơn
- Sau khi tạo, vào chỉnh sửa và bổ sung thêm

---

## 🔐 Bảo mật

⚠️ **CHÚ Ý**: Đây là phiên bản đơn giản cho học tập/demo

Để production, cần:
1. Thay `app.secret_key` bằng key ngẫu nhiên
2. Sử dụng HTTPS
3. Thêm CSRF protection
4. Rate limiting cho API
5. Input validation nghiêm ngặt
6. Sử dụng environment variables cho config

---

## 📝 To-Do List (Tính năng mở rộng)

- [ ] Upload ảnh cho bài viết
- [ ] Danh mục/chuyên mục
- [ ] Bình luận
- [ ] Like/Share
- [ ] Notification
- [ ] Rich text editor
- [ ] Export PDF
- [ ] Analytics
- [ ] Multi-language support

---

## 👥 Hỗ trợ

Nếu gặp vấn đề:
1. Đọc kỹ phần Troubleshooting
2. Kiểm tra console log
3. Kiểm tra database đã tạo chưa

---

## 📄 License

MIT License - Tự do sử dụng cho mục đích học tập và thương mại

---

**© 2026 AI E-Magazine | Tạo bài báo tự động với AI**
