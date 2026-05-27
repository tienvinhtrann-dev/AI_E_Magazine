class Magazine {
  final int id;
  final String name;
  final String description;
  final String slug;
  final String? coverImage;
  final int articleCount;

  const Magazine({
    required this.id,
    required this.name,
    required this.description,
    required this.slug,
    this.coverImage,
    required this.articleCount,
  });

  factory Magazine.fromJson(Map<String, dynamic> json) => Magazine(
        id:           json['id'] as int,
        name:         json['name'] as String? ?? '',
        description:  json['description'] as String? ?? '',
        slug:         json['slug'] as String? ?? '',
        coverImage:   json['cover_image'] as String?,
        articleCount: json['article_count'] as int? ?? 0,
      );
}
