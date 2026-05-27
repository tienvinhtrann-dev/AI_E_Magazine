import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:shimmer/shimmer.dart';

import '../config/app_config.dart';
import '../models/article.dart';
import '../models/magazine.dart';
import '../services/api_service.dart';
import 'home_screen.dart' show ArticleListTile;

class MagazineDetailScreen extends StatefulWidget {
  const MagazineDetailScreen({super.key, required this.magazineId});
  final int magazineId;

  @override
  State<MagazineDetailScreen> createState() => _MagazineDetailScreenState();
}

class _MagazineDetailScreenState extends State<MagazineDetailScreen> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiService().getMagazineDetail(widget.magazineId);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return Scaffold(
            appBar: AppBar(),
            body: const Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.hasError || snap.data == null || snap.data!['ok'] != true) {
          return Scaffold(
            appBar: AppBar(title: const Text('Lỗi')),
            body: const Center(child: Text('Không thể tải tạp chí')),
          );
        }

        final mag = Magazine.fromJson(
            snap.data!['magazine'] as Map<String, dynamic>);
        final rawArticles =
            snap.data!['articles'] as List<dynamic>? ?? [];
        final articles = rawArticles
            .map((e) => Article.fromJson(e as Map<String, dynamic>))
            .toList();

        return Scaffold(
          body: CustomScrollView(
            slivers: [
              SliverAppBar(
                expandedHeight: 200,
                pinned: true,
                flexibleSpace: FlexibleSpaceBar(
                  title: Text(mag.name,
                      style: const TextStyle(
                          shadows: [Shadow(blurRadius: 6)])),
                  background: mag.coverImage != null &&
                          mag.coverImage!.isNotEmpty
                      ? CachedNetworkImage(
                          imageUrl:
                              '${AppConfig.baseUrl}${mag.coverImage}',
                          fit: BoxFit.cover,
                          errorWidget: (_, __, ___) => _headerPlaceholder(),
                        )
                      : _headerPlaceholder(),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (mag.description.isNotEmpty)
                        Text(mag.description,
                            style: const TextStyle(color: Colors.grey)),
                      const SizedBox(height: 8),
                      Text(
                        '${mag.articleCount} bài viết',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.primary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const Divider(height: 24),
                      const Text(
                        'Danh sách bài viết',
                        style: TextStyle(
                            fontWeight: FontWeight.bold, fontSize: 16),
                      ),
                    ],
                  ),
                ),
              ),
              articles.isEmpty
                  ? const SliverToBoxAdapter(
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Center(child: Text('Chưa có bài viết')),
                      ),
                    )
                  : SliverList(
                      delegate: SliverChildBuilderDelegate(
                        (ctx, i) => ArticleListTile(article: articles[i]),
                        childCount: articles.length,
                      ),
                    ),
              const SliverPadding(padding: EdgeInsets.only(bottom: 16)),
            ],
          ),
        );
      },
    );
  }

  Widget _headerPlaceholder() => Container(
        color: const Color(0xFF1565C0),
        child: const Center(
            child: Icon(Icons.auto_stories, size: 60, color: Colors.white)),
      );
}
