import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter_html/flutter_html.dart';

import '../config/app_config.dart';
import '../models/article.dart';
import '../services/api_service.dart';

class ArticleDetailScreen extends StatefulWidget {
  const ArticleDetailScreen({super.key, required this.articleId});
  final int articleId;

  @override
  State<ArticleDetailScreen> createState() => _ArticleDetailScreenState();
}

class _ArticleDetailScreenState extends State<ArticleDetailScreen> {
  late Future<Article> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiService().getArticle(widget.articleId);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Article>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return Scaffold(
            appBar: AppBar(),
            body: const Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.hasError || snap.data == null) {
          return Scaffold(
            appBar: AppBar(title: const Text('Lỗi')),
            body: Center(
              child: Text(
                snap.hasError
                    ? 'Lỗi: ${snap.error}'
                    : 'Không thể tải bài viết',
              ),
            ),
          );
        }

        final article = snap.data!;
        return Scaffold(
          appBar: AppBar(
            title: Text(
              article.category.isNotEmpty ? article.category : 'Bài viết',
              style: const TextStyle(fontSize: 14),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.share),
                onPressed: () {},
              ),
            ],
          ),
          body: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Title
                Text(
                  article.title,
                  style: const TextStyle(
                      fontSize: 22, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),

                // Meta row
                Row(
                  children: [
                    Icon(Icons.remove_red_eye,
                        size: 14,
                        color: Theme.of(context).colorScheme.outline),
                    const SizedBox(width: 4),
                    Text(
                      '${article.viewCount} lượt xem',
                      style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.outline),
                    ),
                    const SizedBox(width: 16),
                    if (article.createdAt.isNotEmpty) ...[
                      Icon(Icons.calendar_today,
                          size: 14,
                          color: Theme.of(context).colorScheme.outline),
                      const SizedBox(width: 4),
                      Flexible(
                        child: Text(
                          _formatDate(article.createdAt),
                          style: TextStyle(
                              fontSize: 12,
                              color: Theme.of(context).colorScheme.outline),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ],
                ),

                const SizedBox(height: 12),

                // Thumbnail
                if (article.thumbnail != null)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: CachedNetworkImage(
                      imageUrl: article.thumbnail!.startsWith('http')
                          ? article.thumbnail!
                          : '${AppConfig.baseUrl}${article.thumbnail}',
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorWidget: (_, __, ___) => const SizedBox.shrink(),
                    ),
                  ),

                const SizedBox(height: 16),

                // Content (HTML)
                Html(
                  data: article.content.isNotEmpty
                      ? article.content
                      : '<p>${article.summary}</p>',
                  style: {
                    'body': Style(
                      fontSize: FontSize(15),
                      lineHeight: LineHeight(1.6),
                    ),
                    'h1': Style(fontSize: FontSize(20)),
                    'h2': Style(fontSize: FontSize(18)),
                    'h3': Style(fontSize: FontSize(16)),
                    'img': Style(width: Width(double.infinity)),
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  String _formatDate(String raw) {
    try {
      final dt = DateTime.parse(raw);
      return '${dt.day}/${dt.month}/${dt.year}';
    } catch (_) {
      return raw;
    }
  }
}
