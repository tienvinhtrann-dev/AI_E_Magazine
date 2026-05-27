import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../config/app_config.dart';
import '../models/user.dart';
import '../services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  User? _user;
  bool _loading = false;
  String? _error;

  User? get user     => _user;
  bool  get isLoggedIn => _user != null;
  bool  get loading  => _loading;
  String? get error  => _error;

  Future<void> checkAuth() async {
    _user = await ApiService().getMe();
    notifyListeners();
  }

  Future<bool> login(String email, String password) async {
    _loading = true;
    _error   = null;
    notifyListeners();
    try {
      final data = await ApiService().login(email, password);
      if (data['ok'] == true) {
        _user    = User.fromJson(data['user'] as Map<String, dynamic>);
        _loading = false;
        notifyListeners();
        return true;
      }
      _error = data['error'] as String? ?? 'Đăng nhập thất bại';
    } catch (_) {
      _error = 'Không thể kết nối đến máy chủ. Kiểm tra URL trong AppConfig.';
    }
    _loading = false;
    notifyListeners();
    return false;
  }

  Future<bool> register(String email, String password, String fullName) async {
    _loading = true;
    _error   = null;
    notifyListeners();
    try {
      final data = await ApiService().register(email, password, fullName);
      if (data['ok'] == true) {
        _loading = false;
        notifyListeners();
        return true;
      }
      _error = data['error'] as String? ?? 'Đăng ký thất bại';
    } catch (_) {
      _error = 'Không thể kết nối đến máy chủ.';
    }
    _loading = false;
    notifyListeners();
    return false;
  }

  Future<void> logout() async {
    await ApiService().logout();
    try {
      await GoogleSignIn().signOut();
    } catch (_) {}
    _user = null;
    notifyListeners();
  }

  Future<bool> signInWithGoogle() async {
    _loading = true;
    _error   = null;
    notifyListeners();
    try {
      final googleSignIn = GoogleSignIn(
        serverClientId: AppConfig.googleWebClientId,
        scopes: ['email', 'profile'],
      );
      final account = await googleSignIn.signIn();
      if (account == null) {
        // User cancelled
        _loading = false;
        notifyListeners();
        return false;
      }
      final auth     = await account.authentication;
      final idToken  = auth.idToken;
      if (idToken == null) {
        _error = 'Không lấy được token từ Google';
        _loading = false;
        notifyListeners();
        return false;
      }
      final data = await ApiService().loginWithGoogle(idToken);
      if (data['ok'] == true) {
        _user    = User.fromJson(data['user'] as Map<String, dynamic>);
        _loading = false;
        notifyListeners();
        return true;
      }
      _error = data['error'] as String? ?? 'Đăng nhập Google thất bại';
    } catch (e) {
      final msg = e.toString();
      if (msg.contains('Connection refused') || msg.contains('connection error')) {
        _error =
            'Không kết nối được server ${AppConfig.baseUrl}. '
            'Emulator dùng http://10.0.2.2:5000, điện thoại thật dùng http://<IP_PC>:5000 rồi build lại app.';
      } else {
        _error = 'Lỗi đăng nhập Google: $msg';
      }
    }
    _loading = false;
    notifyListeners();
    return false;
  }
}
