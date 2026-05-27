import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth   = context.watch<AuthProvider>();
    final user   = auth.user;
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Tài khoản của tôi')),
      body: user == null
          ? _notLoggedIn(context)
          : _loggedIn(context, user, scheme),
    );
  }

  Widget _notLoggedIn(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.person_off, size: 64, color: Colors.grey),
          const SizedBox(height: 12),
          const Text('Bạn chưa đăng nhập'),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () => Navigator.pushNamed(context, '/login'),
            child: const Text('Đăng nhập'),
          ),
        ],
      ),
    );
  }

  Widget _loggedIn(BuildContext context, user, ColorScheme scheme) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        // Avatar
        Center(
          child: CircleAvatar(
            radius: 42,
            backgroundColor: scheme.primaryContainer,
            child: Text(
              user.name.isNotEmpty ? user.name[0].toUpperCase() : '?',
              style: TextStyle(
                  fontSize: 36,
                  fontWeight: FontWeight.bold,
                  color: scheme.primary),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Center(
          child: Text(user.name,
              style: const TextStyle(
                  fontSize: 20, fontWeight: FontWeight.bold)),
        ),
        Center(
          child: Text(user.email,
              style: const TextStyle(color: Colors.grey)),
        ),
        const SizedBox(height: 24),

        // Info card
        Card(
          child: Column(
            children: [
              ListTile(
                leading: const Icon(Icons.badge_outlined),
                title: const Text('Vai trò'),
                trailing: Chip(
                  label: Text(user.isAdmin ? 'Admin' : 'Thành viên'),
                  backgroundColor: user.isAdmin
                      ? scheme.primaryContainer
                      : scheme.surfaceVariant,
                ),
              ),
              const Divider(height: 1, indent: 16, endIndent: 16),
              ListTile(
                leading: const Icon(Icons.toll_outlined),
                title: const Text('Token còn lại'),
                trailing: Text(
                  '${user.tokens}',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: scheme.primary,
                  ),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),

        // Logout
        OutlinedButton.icon(
          onPressed: () async {
            await context.read<AuthProvider>().logout();
            if (!context.mounted) return;
            Navigator.pushReplacementNamed(context, '/login');
          },
          icon: const Icon(Icons.logout),
          label: const Text('Đăng xuất'),
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.red,
            side: const BorderSide(color: Colors.red),
            padding: const EdgeInsets.symmetric(vertical: 12),
          ),
        ),
      ],
    );
  }
}
