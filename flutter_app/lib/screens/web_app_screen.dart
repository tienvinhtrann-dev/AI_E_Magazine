import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../config/app_config.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';

class WebAppScreen extends StatefulWidget {
  const WebAppScreen({super.key});

  @override
  State<WebAppScreen> createState() => _WebAppScreenState();
}

class _WebAppScreenState extends State<WebAppScreen> {
  late final WebViewController _controller;
  late final WebViewCookieManager _cookieManager;
  final _progress = ValueNotifier<int>(0);
  final _title = ValueNotifier<String?>(null);
  final _canGoBack = ValueNotifier<bool>(false);
  bool _handlingGoogle = false;

  @override
  void initState() {
    super.initState();

    _cookieManager = WebViewCookieManager();

    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.white)
      ..setNavigationDelegate(
        NavigationDelegate(
          onNavigationRequest: (req) async {
            final uri = Uri.tryParse(req.url);
            if (uri == null) return NavigationDecision.navigate;

            // Google chặn login trong WebView -> dùng native Google Sign-In.
            if (_isGoogleAuthUrl(uri)) {
              await _handleGoogleLogin();
              return NavigationDecision.prevent;
            }

            return NavigationDecision.navigate;
          },
          onProgress: (p) => _progress.value = p,
          onPageFinished: (_) async {
            _title.value = await _controller.getTitle();
            _canGoBack.value = await _controller.canGoBack();
          },
        ),
      )
      ..loadRequest(
        Uri.parse(AppConfig.baseUrl),
        headers: const {'ngrok-skip-browser-warning': 'true'},
      );
  }

  bool _isGoogleAuthUrl(Uri uri) {
    final host = uri.host.toLowerCase();
    if (host.contains('accounts.google.com')) return true;
    if (host.contains('oauth2.googleapis.com')) return true;
    if (host.contains('gsi') && host.contains('google')) return true;

    // Nhiều site dùng /auth/google để redirect sang Google.
    final path = uri.path.toLowerCase();
    if (path.contains('/auth/google')) return true;

    return false;
  }

  Future<void> _syncCookiesToWebView() async {
    final cookies = await ApiService().getCookiesForBaseUrl();
    final base = Uri.parse(AppConfig.baseUrl);

    for (final c in cookies) {
      // Đảm bảo domain/path hợp lệ cho WebView cookie jar.
      final domain = (c.domain?.isNotEmpty == true) ? c.domain! : base.host;
      final path = (c.path?.isNotEmpty == true) ? c.path! : '/';
      await _cookieManager.setCookie(
        WebViewCookie(
          name: c.name,
          value: c.value,
          domain: domain.startsWith('.') ? domain.substring(1) : domain,
          path: path,
        ),
      );
    }
  }

  Future<void> _handleGoogleLogin() async {
    if (_handlingGoogle) return;
    _handlingGoogle = true;

    if (!mounted) return;
    final auth = context.read<AuthProvider>();

    // Hiển thị loading đơn giản trong lúc native sign-in.
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => const AlertDialog(
        content: Row(
          children: [
            SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
            SizedBox(width: 12),
            Expanded(child: Text('Đang đăng nhập Google...')),
          ],
        ),
      ),
    );

    final ok = await auth.signInWithGoogle();
    if (mounted) Navigator.of(context, rootNavigator: true).pop();

    if (ok) {
      await _syncCookiesToWebView();
      await _controller.loadRequest(
        Uri.parse(AppConfig.baseUrl),
        headers: const {'ngrok-skip-browser-warning': 'true'},
      );
    } else if (mounted && auth.error != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(auth.error!), backgroundColor: Colors.redAccent),
      );
    }

    _handlingGoogle = false;
  }

  @override
  void dispose() {
    _progress.dispose();
    _title.dispose();
    _canGoBack.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    await _controller.reload();
  }

  Future<void> _backOrExit() async {
    if (await _controller.canGoBack()) {
      await _controller.goBack();
    } else if (mounted) {
      Navigator.maybePop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: ValueListenableBuilder<String?>(
          valueListenable: _title,
          builder: (_, t, __) => Text(t?.trim().isNotEmpty == true ? t! : AppConfig.appName),
        ),
        actions: [
          IconButton(
            tooltip: 'Reload',
            onPressed: _reload,
            icon: const Icon(Icons.refresh),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(2),
          child: ValueListenableBuilder<int>(
            valueListenable: _progress,
            builder: (_, p, __) => p >= 100
                ? const SizedBox(height: 2)
                : LinearProgressIndicator(value: p / 100.0, minHeight: 2),
          ),
        ),
      ),
      body: WillPopScope(
        onWillPop: () async {
          await _backOrExit();
          return false;
        },
        child: WebViewWidget(controller: _controller),
      ),
      floatingActionButton: ValueListenableBuilder<bool>(
        valueListenable: _canGoBack,
        builder: (_, canBack, __) => FloatingActionButton.small(
          onPressed: _backOrExit,
          tooltip: canBack ? 'Back' : 'Close',
          child: Icon(canBack ? Icons.arrow_back : Icons.close),
        ),
      ),
    );
  }
}

