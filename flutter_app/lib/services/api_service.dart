import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:cookie_jar/cookie_jar.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';

import '../config/app_config.dart';
import '../models/article.dart';
import '../models/magazine.dart';
import '../models/user.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  late final Dio _dio;
  late final PersistCookieJar _cookieJar;
  bool _initialized = false;

  Future<void> init() async {
    if (_initialized) return;
    final dir = await getApplicationDocumentsDirectory();
    _cookieJar = PersistCookieJar(
      ignoreExpires: false,
      storage: FileStorage('${dir.path}/.cookies/'),
    );
    _dio = Dio(
      BaseOptions(
        baseUrl:        AppConfig.baseUrl,
        connectTimeout: AppConfig.connectTimeout,
        receiveTimeout: AppConfig.receiveTimeout,
        headers: {'Content-Type': 'application/json'},
      ),
    );
    _dio.interceptors.add(CookieManager(_cookieJar));
    _initialized = true;
  }

  Future<List<Cookie>> getCookiesForBaseUrl() async {
    await init();
    return _cookieJar.loadForRequest(Uri.parse(AppConfig.baseUrl));
  }

  // ------------------------------------------------------------------ //
  // Auth                                                                 //
  // ------------------------------------------------------------------ //

  Future<Map<String, dynamic>> login(String email, String password) async {
    final resp = await _dio.post(
      '/api/login',
      data: {'email': email, 'password': password},
    );
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> register(
      String email, String password, String fullName) async {
    final resp = await _dio.post(
      '/api/register',
      data: {'email': email, 'password': password, 'full_name': fullName},
    );
    return resp.data as Map<String, dynamic>;
  }

  Future<void> logout() async {
    try {
      await _dio.post('/api/logout');
    } catch (_) {}
    await _cookieJar.deleteAll();
  }

  Future<Map<String, dynamic>> loginWithGoogle(String idToken) async {
    final resp = await _dio.post(
      '/api/auth/google',
      data: {'id_token': idToken},
    );
    return resp.data as Map<String, dynamic>;
  }

  Future<User?> getMe() async {
    try {
      final resp = await _dio.get('/api/me');
      final data = resp.data as Map<String, dynamic>;
      if (data['ok'] == true) {
        return User.fromJson(data['user'] as Map<String, dynamic>);
      }
    } catch (_) {}
    return null;
  }

  // ------------------------------------------------------------------ //
  // Magazines                                                            //
  // ------------------------------------------------------------------ //

  Future<List<Magazine>> getMagazines() async {
    final resp = await _dio.get('/api/magazines');
    final data = resp.data as Map<String, dynamic>;
    final list = data['magazines'] as List<dynamic>? ?? [];
    return list.map((e) => Magazine.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> getMagazineDetail(int id) async {
    final resp = await _dio.get('/api/magazine/$id');
    return resp.data as Map<String, dynamic>;
  }

  // ------------------------------------------------------------------ //
  // Articles                                                             //
  // ------------------------------------------------------------------ //

  Future<Article> getArticle(int id) async {
    final resp = await _dio.get('/api/article/$id');
    final data = resp.data as Map<String, dynamic>;
    return Article.fromJson(data['article'] as Map<String, dynamic>);
  }

  Future<List<Article>> getTrendingArticles() async {
    final resp = await _dio.get('/api/articles/trending');
    final data = resp.data as Map<String, dynamic>;
    final list = data['articles'] as List<dynamic>? ?? [];
    return list.map((e) => Article.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Article>> search(String query) async {
    final resp = await _dio.get('/api/search', queryParameters: {'q': query});
    final data = resp.data as Map<String, dynamic>;
    final list = data['results'] as List<dynamic>? ?? [];
    return list.map((e) => Article.fromJson(e as Map<String, dynamic>)).toList();
  }
}
