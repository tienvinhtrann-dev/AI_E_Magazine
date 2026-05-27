# Hướng dẫn Build APK – AI E-Magazine Flutter App

## Cấu trúc project tạo sẵn

```
flutter_app/
├── pubspec.yaml
├── android/app/src/main/AndroidManifest.xml
└── lib/
    ├── main.dart
    ├── config/app_config.dart
    ├── models/  (article.dart, magazine.dart, user.dart)
    ├── services/api_service.dart
    ├── providers/auth_provider.dart
    └── screens/ (splash, login, register, home, magazine_detail,
                   article_detail, search, profile)
```

---

## Bước 1 – Cài đặt môi trường

### 1.1 Cài Java JDK 17
Tải tại: https://www.oracle.com/java/technologies/downloads/#java17

Kiểm tra: `java -version`

### 1.2 Cài Flutter SDK
1. Tải Flutter: https://docs.flutter.dev/get-started/install/windows
2. Giải nén vào `C:\flutter`
3. Thêm `C:\flutter\bin` vào biến môi trường **PATH**
4. Mở terminal mới, chạy: `flutter doctor`

### 1.3 Cài Android Studio (để có Android SDK)
Tải tại: https://developer.android.com/studio

Sau khi cài:
- Mở Android Studio → **SDK Manager**
- Cài **Android SDK Platform 33+** và **Android SDK Build-Tools**
- Cài **Android SDK Command-line Tools**

### 1.4 Chấp nhận Android licenses
```bash
flutter doctor --android-licenses
```
(Nhập `y` cho tất cả)

---

## Bước 2 – Tạo Flutter project

```bash
cd c:\xampp\htdocs\ai_e_magazine

# Tạo project mới
flutter create flutter_app --org com.aimagazine --project-name ai_magazine

# Xác nhận ghi đè pubspec.yaml và lib/ khi được hỏi
```

> Hoặc chạy lệnh sau để bỏ qua xác nhận:
> ```bash
> flutter create flutter_app --org com.aimagazine --project-name ai_magazine --overwrite
> ```

---

## Bước 3 – Sao chép source code đã tạo sẵn

Các file trong `flutter_app/lib/` và `flutter_app/pubspec.yaml` đã được tạo sẵn.
Sau khi chạy `flutter create`, chỉ cần cập nhật `AndroidManifest.xml`:

```bash
# File đã có sẵn tại:
# flutter_app/android/app/src/main/AndroidManifest.xml
# (đã có INTERNET permission và usesCleartextTraffic=true)
```

---

## Bước 4 – Cấu hình URL backend

Mở file `flutter_app/lib/config/app_config.dart` và chỉnh `baseUrl`:

| Trường hợp | URL |
|---|---|
| Android Emulator | `http://10.0.2.2:5000` ✅ (mặc định) |
| Thiết bị thật cùng WiFi | `http://192.168.x.x:5000` |
| Ngrok (public) | `https://clean-cathedral-rocking.ngrok-free.dev` |

---

## Bước 5 – Cài dependencies và build APK

```bash
cd c:\xampp\htdocs\ai_e_magazine\flutter_app

# Cài packages
flutter pub get

# Build APK debug (nhanh, để test)
flutter build apk --debug

# Build APK release (tối ưu, để phân phối)
flutter build apk --release
```

APK output sẽ ở:
```
flutter_app\build\app\outputs\flutter-apk\app-release.apk
```

---

## Bước 6 – Cài APK lên điện thoại

**Cách 1 – Kết nối USB:**
```bash
# Bật Developer Options + USB Debugging trên điện thoại
flutter devices        # Kiểm tra thiết bị đã kết nối
flutter install        # Cài trực tiếp
```

**Cách 2 – Copy file APK:**
```
flutter_app\build\app\outputs\flutter-apk\app-release.apk
```
Copy file này sang điện thoại và cài thủ công (bật "Cài từ nguồn không rõ").

---

## Lưu ý quan trọng

- Flask server phải đang chạy trên port 5000 khi dùng app
- Với Android Emulator, dùng `10.0.2.2:5000` thay vì `localhost:5000`
- Trên thiết bị thật, máy tính và điện thoại phải cùng mạng WiFi
- Để phát hành lên CH Play, cần ký APK với keystore riêng

---

## Kiểm tra nhanh các API endpoint đã thêm

| Endpoint | Mô tả |
|---|---|
| `POST /api/login` | Đăng nhập |
| `POST /api/register` | Đăng ký |
| `POST /api/logout` | Đăng xuất |
| `GET /api/me` | Thông tin người dùng hiện tại |
| `GET /api/magazines` | Danh sách tạp chí |
| `GET /api/magazine/<id>` | Chi tiết tạp chí + bài viết |
| `GET /api/article/<id>` | Chi tiết bài viết |
| `GET /api/articles/trending` | Bài viết nổi bật |
| `GET /api/search?q=...` | Tìm kiếm |
