import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../config/app_config.dart';
import '../theme/app_colors.dart';
import '../widgets/auth_widgets.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with SingleTickerProviderStateMixin {
  final _formKey   = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _passCtrl  = TextEditingController();
  bool  _obscure   = true;
  late AnimationController _bgCtrl;

  @override
  void initState() {
    super.initState();
    _bgCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 8))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passCtrl.dispose();
    _bgCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final auth = context.read<AuthProvider>();
    final ok   = await auth.login(_emailCtrl.text.trim(), _passCtrl.text);
    if (!mounted) return;
    if (ok) {
      Navigator.pushReplacementNamed(context, '/home');
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(auth.error ?? 'Đăng nhập thất bại'),
        backgroundColor: Colors.redAccent,
      ));
    }
  }

  Future<void> _signInWithGoogle() async {
    final auth = context.read<AuthProvider>();
    final ok   = await auth.signInWithGoogle();
    if (!mounted) return;
    if (ok) {
      Navigator.pushReplacementNamed(context, '/home');
    } else if (auth.error != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(auth.error!),
        backgroundColor: Colors.redAccent,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final size = MediaQuery.of(context).size;

    return Scaffold(
      body: Stack(
        children: [
          // Gradient background
          Container(decoration: const BoxDecoration(gradient: AppColors.authBgGradient)),

          // Animated decorative circles
          AnimatedBuilder(
            animation: _bgCtrl,
            builder: (_, __) => Stack(children: [
              _circle(color: const Color(0x33667EEA), size: 320,
                  left: -80 + _bgCtrl.value * 20, top: -60 + _bgCtrl.value * 15),
              _circle(color: const Color(0x22764BA2), size: 260,
                  left: size.width - 120 + _bgCtrl.value * -15,
                  top: size.height * 0.4 + _bgCtrl.value * 20),
              _circle(color: const Color(0x1A667EEA), size: 200,
                  left: size.width * 0.2 + _bgCtrl.value * 10,
                  top: size.height - 180 + _bgCtrl.value * -10),
            ]),
          ),

          // Main content
          SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 420),
                  child: Container(
                    padding: const EdgeInsets.fromLTRB(28, 36, 28, 28),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(color: Colors.black.withOpacity(0.10),
                            blurRadius: 32, offset: const Offset(0, 12))
                      ],
                    ),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          // Logo
                          Center(
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(12),
                              child: Image.network(
                                '${AppConfig.baseUrl}/static/images/logo.png',
                                height: 80, width: 80, fit: BoxFit.contain,
                                errorBuilder: (_, __, ___) => Container(
                                  height: 80, width: 80,
                                  decoration: BoxDecoration(
                                    gradient: AppColors.primaryGradient,
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: const Icon(Icons.auto_stories,
                                      color: Colors.white, size: 40),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),
                          const Text('Đăng nhập',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 26,
                                  fontWeight: FontWeight.w700,
                                  color: AppColors.textTitle)),
                          const SizedBox(height: 6),
                          const Text('Hệ Thống tạo tạp chí bằng AI',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 14,
                                  color: AppColors.textSub)),
                          const SizedBox(height: 8),
                          Text('Server: ${AppConfig.baseUrl}',
                              textAlign: TextAlign.center,
                              style: const TextStyle(fontSize: 11,
                                  color: AppColors.textHint)),
                          const SizedBox(height: 20),

                          // Email field
                          _buildField(
                            ctrl: _emailCtrl,
                            hint: 'Email',
                            icon: Icons.email_outlined,
                            keyboardType: TextInputType.emailAddress,
                            validator: (v) =>
                                (v == null || !v.contains('@'))
                                    ? 'Email không hợp lệ' : null,
                          ),
                          const SizedBox(height: 16),

                          // Password field
                          TextFormField(
                            controller: _passCtrl,
                            obscureText: _obscure,
                            style: const TextStyle(fontSize: 15),
                            decoration: _inputDeco(
                              hint: 'Mật khẩu',
                              prefixIcon: Icons.lock_outline,
                              suffix: GestureDetector(
                                onTap: () =>
                                    setState(() => _obscure = !_obscure),
                                child: Icon(
                                    _obscure
                                        ? Icons.visibility_off_outlined
                                        : Icons.visibility_outlined,
                                    color: const Color(0xFF888888), size: 22),
                              ),
                            ),
                            validator: (v) => (v == null || v.isEmpty)
                                ? 'Nhập mật khẩu' : null,
                          ),
                          const SizedBox(height: 24),

                          // Gradient submit button
                          GradientButton(
                            label: 'Đăng nhập',
                            loading: auth.loading,
                            onPressed: _submit,
                          ),
                          const SizedBox(height: 20),

                          // Separator
                          const AuthSeparator(),
                          const SizedBox(height: 16),

                          // Google button
                          GoogleAuthButton(
                            label: 'Đăng nhập với Google',
                            onPressed: _signInWithGoogle,
                          ),
                          const SizedBox(height: 24),

                          // Link
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Text('Chưa có tài khoản? ',
                                  style: TextStyle(color: AppColors.textSub,
                                      fontSize: 14)),
                              GestureDetector(
                                onTap: () =>
                                    Navigator.pushNamed(context, '/register'),
                                child: const Text('Đăng ký ngay',
                                    style: TextStyle(
                                        color: AppColors.linkColor,
                                        fontWeight: FontWeight.w600,
                                        fontSize: 14)),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _circle({required Color color, required double size,
      required double left, required double top}) {
    return Positioned(
      left: left, top: top,
      child: Container(width: size, height: size,
          decoration: BoxDecoration(shape: BoxShape.circle, color: color)),
    );
  }

  Widget _buildField({
    required TextEditingController ctrl,
    required String hint,
    required IconData icon,
    TextInputType keyboardType = TextInputType.text,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: ctrl,
      keyboardType: keyboardType,
      validator: validator,
      style: const TextStyle(fontSize: 15),
      decoration: _inputDeco(hint: hint, prefixIcon: icon),
    );
  }

  InputDecoration _inputDeco({
    required String hint,
    required IconData prefixIcon,
    Widget? suffix,
  }) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: AppColors.textHint),
      prefixIcon: Icon(prefixIcon, color: AppColors.primary, size: 20),
      suffixIcon: suffix,
      filled: true,
      fillColor: AppColors.inputBg,
      contentPadding:
          const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
      border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: AppColors.inputBorder, width: 2)),
      enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: AppColors.inputBorder, width: 2)),
      focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.primary, width: 2)),
      errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Colors.redAccent, width: 2)),
      focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Colors.redAccent, width: 2)),
    );
  }
}
