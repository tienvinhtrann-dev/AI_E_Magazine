class AppConfig {
  // ---------------------------------------------------------------
  // Thay đổi baseUrl tùy môi trường:
  //   - Android emulator  → http://10.0.2.2:5000
  //   - Thiết bị thật     → http://<IP_máy_tính>:5000
  //   - Ngrok / deploy    → https://your-ngrok-url.ngrok-free.dev
  // ---------------------------------------------------------------
  // Ưu tiên cấu hình qua build flag:
  //   flutter run --dart-define=BASE_URL=http://10.0.2.2:5000          (Android emulator)
  //   flutter run --dart-define=BASE_URL=http://192.168.1.105:5000    (điện thoại thật)
  //   flutter build apk --dart-define=BASE_URL=https://your-domain.com
  //
  // Mặc định: 10.0.2.2 = localhost của máy host khi chạy Android emulator.
  static const String baseUrl =
      String.fromEnvironment('BASE_URL', defaultValue: 'http://10.0.2.2:5000');

  static const String appName = 'AI E-Magazine';

  // Google Sign-In: lấy từ Google Cloud Console → APIs & Services → Credentials
  // Tạo "OAuth 2.0 Client ID" loại "Web application"
  static const String googleWebClientId =
      '331470394438-uamnlj96dahaadb4eteagvl5278q3kvu.apps.googleusercontent.com';
  static const Duration connectTimeout = Duration(seconds: 10);
  static const Duration receiveTimeout = Duration(seconds: 20);
}
