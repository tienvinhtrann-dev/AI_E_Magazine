# 🚀 HƯỚNG DẪN NHANH - 3 BƯỚC

## ⚡ Quick Start (Chạy ngay trong 3 bước)

### **Bước 1: Start MySQL**
1. Mở **XAMPP Control Panel**
2. Click **Start** cho MySQL
3. Đợi đến khi chữ "MySQL" chuyển màu xanh

### **Bước 2: Chạy script tự động**
```bash
cd c:\xampp\htdocs\ai_e_magazine
start_simple.bat
```

Script sẽ tự động:
- ✅ Kiểm tra MySQL
- ✅ Cài đặt Python packages
- ✅ Tạo database
- ✅ Khởi động server

### **Bước 3: Truy cập ứng dụng**
Mở trình duyệt: **http://127.0.0.1:5000**

---

## 🔑 Tài khoản Admin mặc định

```
Email: admin@magazine.com
Password: admin123
```

---

## 💡 Cách sử dụng

1. **Đăng nhập** với tài khoản admin
2. Click **✍️ Tạo bài mới**
3. Nhập:
   - Chủ đề: `Trí Tuệ Nhân Tạo`
   - Từ khóa: `trí tuệ nhân tạo, ChatGPT`
4. Click **🚀 Tạo bài báo**
5. Đợi 30-60 giây
6. Chỉnh sửa và **Xuất bản**

---

## ❌ Nếu có lỗi

### MySQL không chạy?
→ Mở XAMPP Control Panel và Start MySQL

### Không cài được package?
```bash
pip install flask mysql-connector-python requests beautifulsoup4
```

### Database lỗi?
```bash
python -c "from database.db_simple import init_database; init_database()"
```

---

## 📖 Tài liệu đầy đủ

Xem file: `SIMPLE_GUIDE.md`

---

**Chúc bạn thành công! 🎉**
