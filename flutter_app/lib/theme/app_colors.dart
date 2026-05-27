import 'package:flutter/material.dart';

class AppColors {
  static const Color primary     = Color(0xFF667EEA);
  static const Color primaryEnd  = Color(0xFF764BA2);
  static const Color teal        = Color(0xFF00FFD5);
  static const Color tealEnd     = Color(0xFF00B375);
  static const Color darkBg      = Color(0xFF080E1F);
  static const Color darkBg2     = Color(0xFF0A1224);
  static const Color cardBg      = Colors.white;
  static const Color inputBg     = Color(0xFFF8F9FC);
  static const Color inputBorder = Color(0xFFE8ECF4);
  static const Color textTitle   = Color(0xFF111827);
  static const Color textSub     = Color(0xFF666666);
  static const Color textHint    = Color(0xFFA0A5B8);
  static const Color linkColor   = Color(0xFF667EEA);

  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primary, primaryEnd],
  );

  static const LinearGradient tealGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [tealEnd, teal],
  );

  static const LinearGradient authBgGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFF0F2FF), Color(0xFFE8F0FE), Color(0xFFF3E8FF)],
  );
}
