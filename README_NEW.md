# 📰 AI E-Magazine - Trang Báo Điện Tử Tự Động

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Tổng quan

**AI E-Magazine** là hệ thống tạo báo điện tử tự động sử dụng AI. Người dùng chỉ cần nhập chủ đề và từ khóa, hệ thống sẽ tự động:

1. 🌐 Crawl tin tức từ các trang báo uy tín (VnExpress, Tuổi Trẻ...)
2. 🤖 Tổng hợp và viết lại thành bài báo hoàn chỉnh
3. 📰 Cho phép chỉnh sửa và xuất bản lên hệ thống

---

## ✨ Tính năng

### 👤 **Quản lý người dùng**
- ✅ Đăng ký / Đăng nhập
- ✅ Phân quyền User / Admin
- ✅ Profile quản lý

### ✍️ **Tạo bài báo tự động**
- ✅ Nhập chủ đề, mô tả, từ khóa
- ✅ AI tự động crawl từ nhiều nguồn
- ✅ Tổng hợp và viết lại bài báo
- ✅ Lưu nguồn tham khảo

### 📊 **Quản lý bài viết**
- ✅ Dashboard với thống kê
- ✅ Quản lý bài viết cá nhân
- ✅ Trạng thái: Draft / Published / Pending
- ✅ Lịch sử chỉnh sửa
- ✅ Đếm lượt xem

### 🔍 **Tìm kiếm & Xem bài**
- ✅ Tìm kiếm full-text
- ✅ Hiển thị bài viết với format đẹp
- ✅ Responsive design

### 👮 **Admin Panel**
- ✅ Quản lý tất cả bài viết
- ✅ Quản lý người dùng
- ✅ Thống kê hệ thống
- ✅ Xóa bài viết không phù hợp

---

## 🚀 Cài đặt Nhanh

### **Yêu cầu hệ thống**
- Python 3.8+
- XAMPP (MySQL)
- Windows/Linux/Mac

### **Cài đặt trong 3 bước**

#### **1. Start MySQL**
Mở XAMPP Control Panel → Start MySQL

#### **2. Chạy script tự động**
```bash
cd c:\xampp\htdocs\ai_e_magazine
start_simple.bat
```

#### **3. Truy cập**
Mở trình duyệt: **http://127.0.0.1:5000**

**Tài khoản Admin:**
- Email: `admin@magazine.com`
- Password: `admin123`

---

## 📖 Tài liệu

- 📘 [**QUICKSTART.md**](QUICKSTART.md) - Hướng dẫn nhanh 3 bước
- 📗 [**SIMPLE_GUIDE.md**](SIMPLE_GUIDE.md) - Hướng dẫn chi tiết đầy đủ

---

## 🏗️ Kiến trúc

```
┌─────────────────────────────────────────────┐
│          USER INTERFACE (Browser)           │
│  Trang chủ | Đăng ký | Tạo bài | Dashboard  │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│          FLASK APPLICATION                   │
│  - Routes & Controllers                      │
│  - Authentication & Authorization            │
│  - Session Management                        │
└───────────────────┬─────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
┌───────▼───────┐      ┌────────▼──────┐
│  AI GENERATOR │      │  DATABASE     │
│  - Crawling   │      │  - Users      │
│  - Processing │      │  - Articles   │
│  - Generation │      │  - History    │
└───────────────┘      └───────────────┘
```

---

## 📁 Cấu trúc thư mục

```
ai_e_magazine/
│
├── 📄 app_simple.py                 # Flask app chính
├── 📄 start_simple.bat              # Script khởi động
├── 📄 requirements_simple.txt       # Dependencies
│
├── 📁 ai/                           # AI Module
│   └── article_generator.py        # Generator chính
│
├── 📁 database/                     # Database Layer
│   ├── db_simple.py                # Connection
│   ├── schema_simple.sql           # Schema
│   ├── user_model_simple.py        # User CRUD
│   └── article_model_simple.py     # Article CRUD
│
└── 📁 templates/                    # HTML Templates
    ├── base.html                   # Base template
    ├── home.html                   # Trang chủ
    ├── login.html / register.html  # Auth
    ├── create_article.html         # Form tạo bài
    ├── generate_progress.html      # Progress page
    ├── article_detail.html         # Chi tiết bài
    ├── edit_article.html           # Chỉnh sửa
    ├── dashboard.html              # Dashboard
    ├── my_articles.html            # Quản lý bài viết
    ├── search_results.html         # Tìm kiếm
    └── admin_panel.html            # Admin
```

---

## 🔧 Công nghệ sử dụng

### **Backend**
- **Flask** 3.0 - Web framework
- **MySQL** - Database
- **Werkzeug** - Password hashing
- **mysql-connector-python** - MySQL driver

### **Web Scraping**
- **Requests** - HTTP client
- **BeautifulSoup4** - HTML parser

### **Frontend**
- **HTML5** / **CSS3**
- **JavaScript** (Vanilla)
- Responsive Design

---

## 📊 Database Schema

### **users**
- Quản lý người dùng và phân quyền

### **articles**
- Lưu trữ bài báo với full metadata
- Status: draft/published/pending
- Source URLs (JSON)
- View count tracking

### **article_history**
- Lịch sử chỉnh sửa bài viết
- Audit trail

### **generation_logs**
- Log quá trình tạo bài
- Performance tracking

---

## 🎨 Screenshots

### Trang chủ
![Home](docs/home.png)

### Tạo bài báo
![Create](docs/create.png)

### Dashboard
![Dashboard](docs/dashboard.png)

---

## 🔐 Bảo mật

⚠️ **LƯU Ý**: Đây là phiên bản đơn giản cho mục đích học tập/demo

Để sử dụng production, cần:
- ✅ Thay secret key
- ✅ Sử dụng HTTPS
- ✅ CSRF protection
- ✅ Rate limiting
- ✅ Input validation
- ✅ Environment variables

---

## 🐛 Troubleshooting

### MySQL không kết nối được?
```
✅ Check XAMPP Control Panel
✅ MySQL phải đang chạy (màu xanh)
✅ Port mặc định: 3306
```

### Không crawl được bài?
```
✅ Kiểm tra kết nối internet
✅ Thử từ khóa tiếng Việt
✅ VnExpress là nguồn ổn định nhất
```

### Lỗi package?
```bash
pip install -r requirements_simple.txt
```

Xem thêm tại [SIMPLE_GUIDE.md](SIMPLE_GUIDE.md)

---

## 📝 To-Do (Tính năng tương lai)

- [ ] Rich text editor (TinyMCE/CKEditor)
- [ ] Upload và quản lý ảnh
- [ ] Danh mục/chuyên mục
- [ ] Hệ thống bình luận
- [ ] Like/Share/Bookmark
- [ ] Email notification
- [ ] Export PDF
- [ ] Analytics dashboard
- [ ] API RESTful
- [ ] Mobile app

---

## 🤝 Đóng góp

Contributions are welcome! 

1. Fork dự án
2. Tạo branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Mở Pull Request

---

## 📄 License

MIT License - Xem file [LICENSE](LICENSE) để biết thêm chi tiết

---

## 👥 Tác giả

**Your Name**
- GitHub: [@yourusername](https://github.com/yourusername)
- Email: your.email@example.com

---

## 🙏 Acknowledgments

- Flask Documentation
- BeautifulSoup4 Documentation
- VnExpress, Tuổi Trẻ (nguồn tin)
- XAMPP Project

---

## 📞 Hỗ trợ

Nếu gặp vấn đề:
1. Đọc [SIMPLE_GUIDE.md](SIMPLE_GUIDE.md)
2. Check [Issues](https://github.com/yourusername/ai-e-magazine/issues)
3. Tạo issue mới

---

**⭐ Nếu thấy hữu ích, hãy cho dự án một star!**

---

© 2026 AI E-Magazine | Made with ❤️ and AI
