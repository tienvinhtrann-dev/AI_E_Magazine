class Comment {
  final int id;
  final String userName;
  final String content;
  final String createdAt;
  final int likes;

  const Comment({
    required this.id,
    required this.userName,
    required this.content,
    required this.createdAt,
    required this.likes,
  });

  factory Comment.fromJson(Map<String, dynamic> json) => Comment(
        id:        json['id'] as int,
        userName:  json['user_name'] as String? ?? 'Ẩn danh',
        content:   json['content'] as String? ?? '',
        createdAt: json['created_at'] as String? ?? '',
        likes:     json['likes'] as int? ?? 0,
      );
}
