// Shared auth widgets used by LoginScreen and RegisterScreen
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

class GradientButton extends StatelessWidget {
  final String label;
  final bool loading;
  final VoidCallback onPressed;

  const GradientButton({
    super.key,
    required this.label,
    required this.loading,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: loading ? null : onPressed,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          gradient: loading
              ? const LinearGradient(
                  colors: [Color(0xFFAAAAAA), Color(0xFF888888)])
              : AppColors.primaryGradient,
          borderRadius: BorderRadius.circular(12),
          boxShadow: loading
              ? []
              : [
                  BoxShadow(
                      color: AppColors.primary.withOpacity(0.3),
                      blurRadius: 15,
                      offset: const Offset(0, 4))
                ],
        ),
        child: loading
            ? const Center(
                child: SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(
                        color: Colors.white, strokeWidth: 2)))
            : Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(label,
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 17,
                          fontWeight: FontWeight.w600)),
                  const SizedBox(width: 8),
                  const Icon(Icons.arrow_forward,
                      color: Colors.white, size: 20),
                ],
              ),
      ),
    );
  }
}

class AuthSeparator extends StatelessWidget {
  const AuthSeparator({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
            child: Container(
                height: 1,
                color: const Color(0xFFE8ECF4))),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 12),
          child: Text('hoặc',
              style: TextStyle(
                  color: Color(0xFF8B93A7), fontSize: 14)),
        ),
        Expanded(
            child: Container(
                height: 1,
                color: const Color(0xFFE8ECF4))),
      ],
    );
  }
}

class GoogleAuthButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;

  const GoogleAuthButton({super.key, required this.label, this.onPressed});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(
              color: const Color(0xFF4285F4).withOpacity(0.28), width: 1),
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 10)
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _GoogleIcon(),
            const SizedBox(width: 12),
            Text(label,
                style: const TextStyle(
                    color: Color(0xFF24405F),
                    fontWeight: FontWeight.w600,
                    fontSize: 15)),
          ],
        ),
      ),
    );
  }
}

class _GoogleIcon extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 20,
      height: 20,
      child: CustomPaint(painter: _GooglePainter()),
    );
  }
}

class _GooglePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final r = size.width / 2;
    final center = Offset(r, r);
    final rect = Rect.fromCircle(center: center, radius: r);
    final paint = Paint()..style = PaintingStyle.fill;

    // Red
    paint.color = const Color(0xFFEA4335);
    canvas.drawArc(rect, -1.2, 2.0, true, paint);
    // Green
    paint.color = const Color(0xFF34A853);
    canvas.drawArc(rect, 0.5, 1.8, true, paint);
    // Yellow
    paint.color = const Color(0xFFFBBC05);
    canvas.drawArc(rect, 2.1, 1.7, true, paint);
    // Blue
    paint.color = const Color(0xFF4285F4);
    canvas.drawArc(rect, 3.6, 1.8, true, paint);
    // White inner circle
    paint.color = Colors.white;
    canvas.drawCircle(center, r * 0.6, paint);
    // Blue right bar
    paint.color = const Color(0xFF4285F4);
    canvas.drawRect(
        Rect.fromLTWH(r, r - r * 0.18, r, r * 0.36), paint);
    // Inner white mask
    paint.color = Colors.white;
    canvas.drawCircle(center, r * 0.55, paint);
  }

  @override
  bool shouldRepaint(_) => false;
}

// Shared input decoration factory
InputDecoration authInputDeco({
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
        borderSide:
            const BorderSide(color: AppColors.primary, width: 2)),
    errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Colors.redAccent, width: 2)),
    focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Colors.redAccent, width: 2)),
  );
}
