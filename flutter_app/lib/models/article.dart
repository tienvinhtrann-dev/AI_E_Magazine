class Article {
  final int id;
  final String title;
  final String content;
  final String summary;
  final String? thumbnail;
  final String category;
  final int? magazineId;
  final String createdAt;
  final int viewCount;

  const Article({
    required this.id,
    required this.title,
    required this.content,
    required this.summary,
    this.thumbnail,
    required this.category,
    this.magazineId,
    required this.createdAt,
    required this.viewCount,
  });

  factory Article.fromJson(Map<String, dynamic> json) => Article(
        id:         json['id'] as int,
        title:      json['title'] as String? ?? '',
        content:    json['content'] as String? ?? '',
        summary:    json['summary'] as String? ?? '',
        thumbnail:  json['thumbnail'] as String?,
        category:   json['category'] as String? ?? '',
        magazineId: json['magazine_id'] as int?,
        createdAt:  json['created_at'] as String? ?? '',
        viewCount:  json['view_count'] as int? ?? 0,
      );
}
