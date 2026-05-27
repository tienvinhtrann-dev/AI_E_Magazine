class User {
  final int id;
  final String email;
  final String name;
  final String role;
  final int tokens;

  const User({
    required this.id,
    required this.email,
    required this.name,
    required this.role,
    required this.tokens,
  });

  bool get isAdmin => role == 'admin';

  factory User.fromJson(Map<String, dynamic> json) => User(
        id:     json['id'] as int,
        email:  json['email'] as String? ?? '',
        name:   json['name'] as String? ?? '',
        role:   json['role'] as String? ?? 'user',
        tokens: json['tokens'] as int? ?? 0,
      );
}
