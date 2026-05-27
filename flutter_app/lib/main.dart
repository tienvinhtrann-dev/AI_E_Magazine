import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'config/app_config.dart';
import 'providers/auth_provider.dart';
import 'services/api_service.dart';
import 'screens/splash_screen.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/home_screen.dart';
import 'screens/web_app_screen.dart';
import 'screens/magazine_detail_screen.dart';
import 'screens/article_detail_screen.dart';
import 'screens/search_screen.dart';
import 'screens/profile_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ApiService().init();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AuthProvider(),
      child: MaterialApp(
        title: AppConfig.appName,
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF1565C0),
          ),
          useMaterial3: true,
        ),
        initialRoute: '/splash',
        routes: {
          '/splash':   (_) => const SplashScreen(),
          // Web wrapper (UI giống web 1:1)
          '/web':      (_) => const WebAppScreen(),
          '/login':    (_) => const LoginScreen(),
          '/register': (_) => const RegisterScreen(),
          '/home':     (_) => const HomeScreen(),
          '/search':   (_) => const SearchScreen(),
          '/profile':  (_) => const ProfileScreen(),
        },
        onGenerateRoute: (settings) {
          if (settings.name == '/magazine') {
            final id = settings.arguments as int;
            return MaterialPageRoute(
              builder: (_) => MagazineDetailScreen(magazineId: id),
            );
          }
          if (settings.name == '/article') {
            final id = settings.arguments as int;
            return MaterialPageRoute(
              builder: (_) => ArticleDetailScreen(articleId: id),
            );
          }
          return null;
        },
      ),
    );
  }
}
