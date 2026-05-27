import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../theme/app_colors.dart';
import '../widgets/auth_widgets.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen>
    with SingleTickerProviderStateMixin {
  final _formKey    = GlobalKey<FormState>();
  final _emailCtrl  = TextEditingController();
  final _passCtrl   = TextEditingController();
  bool  _obscure    = true;
  double _strength  = 0;
  String _strengthLabel = 'Nhập mật khẩu';
  Color  _strengthColor = const Color(0xFFE0E0E0);
  late AnimationController _bgCtrl;

  @override
  void initState() {
    super.initState();
    _bgCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 10))
      ..repeat(reverse: true);
    _passCtrl.addListener(_updateStrength);
  }

  void _updateStrength() {
    final v = _passCtrl.text;
    double s = 0;
    if (v.length >= 6) s += 0.25;
    if (v.length >= 8) s += 0.25;
    if (RegExp(r'[A-Z]').hasMatch(v)) s += 0.25;
    if (RegExp(r'[0-9]').hasMatch(v)) s += 0.25;
    String label;
    Color color;
    if (s == 0) {
      label = 'Nhập mật khẩu'; color = const Color(0xFFE0E0E0);
    } else if (s <= 0.25) {
      label = 'Yếu'; color = Colors.redAccent;
    } else if (s <= 0.50) {
      label = 'Trung bình'; color = Colors.orange;
    } else if (s < 1.0) {
      label = 'Khá mạnh'; color = Colors.lightGreen;
    } else {
      label = 'Mạnh'; color = Colors.green;
    }
    setState(() {
      _strength = s;
      _strengthLabel = label;
      _strengthColor = color;
    });
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
    final ok   = await auth.register(
      _emailCtrl.text.trim(),
      _passCtrl.text,
      _emailCtrl.text.trim(), // use email as default display name
    );
    if (!mounted) return;
    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Đăng ký thành công! Hãy đăng nhập.'),
          backgroundColor: Colors.green,
        ),
      );
      Navigator.pushReplacementNamed(context, '/login');
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(auth.error ?? 'Đăng ký thất bại'),
          backgroundColor: Colors.red,
        ),
      );
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
          Container(
              decoration: const BoxDecoration(
                  gradient: AppColors.authBgGradient)),

          // Animated circles
          AnimatedBuilder(
            animation: _bgCtrl,
            builder: (_, __) => Stack(children: [
              _circle(color: const Color(0x33667EEA), size: 320,
                  left: -80 + _bgCtrl.value * 20,
                  top: -60 + _bgCtrl.value * 15),
              _circle(color: const Color(0x22764BA2), size: 260,
                  left: size.width - 120 + _bgCtrl.value * -15,
                  top: size.height * 0.35 + _bgCtrl.value * 20),
              _circle(color: const Color(0x1A667EEA), size: 200,
                  left: size.width * 0.2 + _bgCtrl.value * 10,
                  top: size.height - 160 + _bgCtrl.value * -10),
            ]),
          ),

          // Content
          SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(
                    horizontal: 24, vertical: 24),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 420),
                  child: Container(
                    padding: const EdgeInsets.fromLTRB(28, 32, 28, 28),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(
                            color: Colors.black.withOpacity(0.10),
                            blurRadius: 32,
                            offset: const Offset(0, 12))
                      ],
                    ),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          // Logo
                          Center(
                            child: Container(
                              height: 72, width: 72,
                              decoration: BoxDecoration(
                                gradient: AppColors.primaryGradient,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(Icons.auto_stories,
                                  color: Colors.white, size: 36),
                            ),
                          ),
                          const SizedBox(height: 14),
                          const Text('Tạo tài khoản',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 24,
                                  fontWeight: FontWeight.w700,
                                  color: AppColors.textTitle)),
                          const SizedBox(height: 5),
                          const Text('Bắt đầu hành trình sáng tạo của bạn',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 14,
                                  color: AppColors.textSub)),
                          const SizedBox(height: 24),

                          // Email
                          TextFormField(
                            controller: _emailCtrl,
                            keyboardType: TextInputType.emailAddress,
                            style: const TextStyle(fontSize: 15),
                            decoration: authInputDeco(
                                hint: 'Email',
                                prefixIcon: Icons.email_outlined),
                            validator: (v) =>
                                (v == null || !v.contains('@'))
                                    ? 'Email không hợp lệ' : null,
                          ),
                          const SizedBox(height: 14),

                          // Password
                          TextFormField(
                            controller: _passCtrl,
                            obscureText: _obscure,
                            style: const TextStyle(fontSize: 15),
                            decoration: authInputDeco(
                              hint: 'Mật khẩu (tối thiểu 6 ký tự)',
                              prefixIcon: Icons.lock_outline,
                              suffix: GestureDetector(
                                onTap: () =>
                                    setState(() => _obscure = !_obscure),
                                child: Icon(
                                    _obscure
                                        ? Icons.visibility_off_outlined
                                        : Icons.visibility_outlined,
                                    color: const Color(0xFF888888),
                                    size: 22),
                              ),
                            ),
                            validator: (v) =>
                                (v == null || v.length < 6)
                                    ? 'Mật khẩu tối thiểu 6 ký tự' : null,
                          ),

                          // Password strength bar
                          const SizedBox(height: 8),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(2),
                            child: LinearProgressIndicator(
                              value: _strength,
                              backgroundColor: const Color(0xFFE0E0E0),
                              valueColor:
                                  AlwaysStoppedAnimation(_strengthColor),
                              minHeight: 4,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Row(children: [
                            const Text('Độ mạnh: ',
                                style: TextStyle(fontSize: 12,
                                    color: AppColors.textSub)),
                            Text(_strengthLabel,
                                style: TextStyle(fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: _strength == 0
                                        ? AppColors.textSub
                                        : _strengthColor)),
                          ]),
                          const SizedBox(height: 18),

                          // Submit button
                          GradientButton(
                            label: 'Đăng ký',
                            loading: auth.loading,
                            onPressed: _submit,
                          ),
                          const SizedBox(height: 18),

                          // Separator
                          const AuthSeparator(),
                          const SizedBox(height: 16),

                          // Google button
                          GoogleAuthButton(
                              label: 'Đăng ký với Google',
                              onPressed: _signInWithGoogle),
                          const SizedBox(height: 22),

                          // Link
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Text('Đã có tài khoản? ',
                                  style: TextStyle(
                                      color: AppColors.textSub, fontSize: 14)),
                              GestureDetector(
                                onTap: () => Navigator.pushNamed(
                                    context, '/login'),
                                child: const Text('Đăng nhập ngay',
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
          decoration:
              BoxDecoration(shape: BoxShape.circle, color: color)),
    );
  }
}
