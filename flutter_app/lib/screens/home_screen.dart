import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:shimmer/shimmer.dart';
import 'package:provider/provider.dart';

import '../config/app_config.dart';
import '../models/article.dart';
import '../models/magazine.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import 'profile_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  final _pages = const [_DiscoverTab(), _SearchTab(), _ProfileTab()];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _pages[_currentIndex],
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(
              top: BorderSide(color: Color(0xFFE8ECF4), width: 1)),
        ),
        child: NavigationBar(
          backgroundColor: Colors.white,
          indicatorColor: AppColors.primary.withOpacity(0.12),
          selectedIndex: _currentIndex,
          labelBehavior:
              NavigationDestinationLabelBehavior.onlyShowSelected,
          onDestinationSelected: (i) =>
              setState(() => _currentIndex = i),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.home_outlined, color: Color(0xFF8B93A7)),
              selectedIcon:
                  Icon(Icons.home, color: AppColors.primary),
              label: 'Khám phá',
            ),
            NavigationDestination(
              icon: Icon(Icons.search, color: Color(0xFF8B93A7)),
              selectedIcon:
                  Icon(Icons.search, color: AppColors.primary),
              label: 'Tìm kiếm',
            ),
            NavigationDestination(
              icon: Icon(Icons.person_outlined,
                  color: Color(0xFF8B93A7)),
              selectedIcon:
                  Icon(Icons.person, color: AppColors.primary),
              label: 'Tôi',
            ),
          ],
        ),
      ),
    );
  }
}

// ------------------------------------------------------------------ //
// Tab 1 – Discover                                                     //
// ------------------------------------------------------------------ //
class _DiscoverTab extends StatefulWidget {
  const _DiscoverTab();

  @override
  State<_DiscoverTab> createState() => _DiscoverTabState();
}

class _DiscoverTabState extends State<_DiscoverTab> {
  late Future<List<Magazine>> _magsFuture;
  late Future<List<Article>>  _trendFuture;

  @override
  void initState() {
    super.initState();
    _magsFuture  = ApiService().getMagazines();
    _trendFuture = ApiService().getTrendingArticles();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F6FC),
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(70),
        child: Container(
          decoration: const BoxDecoration(
            gradient: AppColors.primaryGradient,
          ),
          child: SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
              child: Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.auto_stories,
                        color: Colors.white, size: 20),
                  ),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('AI E-Magazine',
                            style: TextStyle(
                                color: Colors.white,
                                fontSize: 17,
                                fontWeight: FontWeight.w700)),
                        Text('Khám phá tạp chí',
                            style: TextStyle(
                                color: Colors.white70, fontSize: 12)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          setState(() {
            _magsFuture  = ApiService().getMagazines();
            _trendFuture = ApiService().getTrendingArticles();
          });
        },
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: 8),
          children: [
            _SectionTitle('Tạp chí'),
            _MagazineRow(future: _magsFuture),
            _SectionTitle('Bài viết nổi bật'),
            _TrendingList(future: _trendFuture),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);
  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 10),
      child: Row(
        children: [
          Container(
            width: 4, height: 18,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Text(title,
              style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textTitle)),
        ],
      ),
    );
  }
}

class _MagazineRow extends StatelessWidget {
  const _MagazineRow({required this.future});
  final Future<List<Magazine>> future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Magazine>>(
      future: future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return _shimmerRow();
        }
        if (snap.hasError || snap.data == null || snap.data!.isEmpty) {
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Text('Chưa có tạp chí nào.'),
          );
        }
        final mags = snap.data!;
        return SizedBox(
          height: 160,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            itemCount: mags.length,
            itemBuilder: (ctx, i) => _MagazineCard(mag: mags[i]),
          ),
        );
      },
    );
  }

  Widget _shimmerRow() {
    return SizedBox(
      height: 160,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        itemCount: 4,
        itemBuilder: (_, __) => Shimmer.fromColors(
          baseColor: Colors.grey.shade300,
          highlightColor: Colors.grey.shade100,
          child: Container(
            width: 120,
            margin: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(10),
            ),
          ),
        ),
      ),
    );
  }
}

class _MagazineCard extends StatelessWidget {
  const _MagazineCard({required this.mag});
  final Magazine mag;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () =>
          Navigator.pushNamed(context, '/magazine', arguments: mag.id),
      child: Container(
        width: 130,
        margin: const EdgeInsets.only(left: 4, right: 8, top: 4, bottom: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
                color: AppColors.primary.withOpacity(0.10),
                blurRadius: 12,
                offset: const Offset(0, 4))
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(14)),
              child: mag.coverImage != null && mag.coverImage!.isNotEmpty
                  ? CachedNetworkImage(
                      imageUrl: '${AppConfig.baseUrl}${mag.coverImage}',
                      height: 95,
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorWidget: (_, __, ___) => _placeholder(),
                    )
                  : _placeholder(),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    mag.name,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textTitle),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      gradient: AppColors.primaryGradient,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      '${mag.articleCount} bài',
                      style: const TextStyle(
                          fontSize: 10,
                          color: Colors.white,
                          fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _placeholder() => Container(
        height: 95,
        decoration: const BoxDecoration(
          gradient: AppColors.primaryGradient,
        ),
        child: const Center(
            child: Icon(Icons.auto_stories,
                size: 32, color: Colors.white)),
      );
}

class _TrendingList extends StatelessWidget {
  const _TrendingList({required this.future});
  final Future<List<Article>> future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Article>>(
      future: future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return _shimmerList();
        }
        if (snap.hasError || snap.data == null || snap.data!.isEmpty) {
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Text('Chưa có bài viết.'),
          );
        }
        return Column(
          children: snap.data!
              .map((a) => ArticleListTile(article: a))
              .toList(),
        );
      },
    );
  }

  Widget _shimmerList() {
    return Column(
      children: List.generate(
        4,
        (_) => Shimmer.fromColors(
          baseColor: Colors.grey.shade300,
          highlightColor: Colors.grey.shade100,
          child: Container(
            height: 80,
            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ),
      ),
    );
  }
}

// Shared article list tile (reused across tabs)
class ArticleListTile extends StatelessWidget {
  const ArticleListTile({super.key, required this.article});
  final Article article;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () =>
          Navigator.pushNamed(context, '/article', arguments: article.id),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
                color: Colors.black.withOpacity(0.06),
                blurRadius: 10,
                offset: const Offset(0, 3))
          ],
        ),
        child: Row(
          children: [
            // Thumbnail
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: SizedBox(
                width: 72, height: 72,
                child: article.thumbnail != null
                    ? CachedNetworkImage(
                        imageUrl: article.thumbnail!.startsWith('http')
                            ? article.thumbnail!
                            : '${AppConfig.baseUrl}${article.thumbnail}',
                        fit: BoxFit.cover,
                        errorWidget: (_, __, ___) => _thumbPlaceholder(),
                      )
                    : _thumbPlaceholder(),
              ),
            ),
            const SizedBox(width: 12),
            // Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (article.category.isNotEmpty)
                    Container(
                      margin: const EdgeInsets.only(bottom: 4),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withOpacity(0.10),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(article.category,
                          style: const TextStyle(
                              fontSize: 10,
                              color: AppColors.primary,
                              fontWeight: FontWeight.w600)),
                    ),
                  Text(
                    article.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 13,
                        color: AppColors.textTitle),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.remove_red_eye_outlined,
                          size: 12, color: AppColors.textSub),
                      const SizedBox(width: 3),
                      Text('${article.viewCount} lượt xem',
                          style: const TextStyle(
                              fontSize: 11, color: AppColors.textSub)),
                    ],
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right,
                color: Color(0xFFCCCCCC), size: 20),
          ],
        ),
      ),
    );
  }

  Widget _thumbPlaceholder() => Container(
        decoration: const BoxDecoration(
          gradient: AppColors.primaryGradient,
        ),
        child: const Icon(Icons.article, color: Colors.white),
      );
}

// ------------------------------------------------------------------ //
// Tab 2 – Search (inline)                                             //
// ------------------------------------------------------------------ //
class _SearchTab extends StatefulWidget {
  const _SearchTab();

  @override
  State<_SearchTab> createState() => _SearchTabState();
}

class _SearchTabState extends State<_SearchTab> {
  final _ctrl = TextEditingController();
  List<Article>? _results;
  bool _loading = false;

  Future<void> _search(String q) async {
    if (q.trim().isEmpty) {
      setState(() => _results = null);
      return;
    }
    setState(() => _loading = true);
    final r = await ApiService().search(q.trim());
    if (!mounted) return;
    setState(() {
      _results = r;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F6FC),
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(70),
        child: Container(
          decoration: const BoxDecoration(
            gradient: AppColors.primaryGradient,
          ),
          child: SafeArea(
            child: Padding(
              padding:
                  const EdgeInsets.fromLTRB(16, 0, 16, 10),
              child: Row(
                children: [
                  Expanded(
                    child: Container(
                      height: 40,
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.20),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: TextField(
                        controller: _ctrl,
                        autofocus: false,
                        textInputAction: TextInputAction.search,
                        onSubmitted: _search,
                        style: const TextStyle(
                            color: Colors.white, fontSize: 14),
                        decoration: InputDecoration(
                          hintText: 'Tìm kiếm bài viết...',
                          hintStyle: TextStyle(
                              color: Colors.white.withOpacity(0.70),
                              fontSize: 14),
                          prefixIcon: const Icon(Icons.search,
                              color: Colors.white, size: 20),
                          border: InputBorder.none,
                          contentPadding:
                              const EdgeInsets.symmetric(vertical: 10),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: () => _search(_ctrl.text),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.20),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Text('Tìm',
                          style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                              fontSize: 14)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(
                  color: AppColors.primary))
          : _results == null
              ? const Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.search, size: 60,
                          color: Color(0xFFCCCCCC)),
                      SizedBox(height: 12),
                      Text('Nhập từ khóa để tìm kiếm',
                          style: TextStyle(
                              color: AppColors.textSub, fontSize: 15)),
                    ],
                  ),
                )
              : _results!.isEmpty
                  ? const Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.search_off, size: 60,
                              color: Color(0xFFCCCCCC)),
                          SizedBox(height: 12),
                          Text('Không tìm thấy kết quả',
                              style: TextStyle(
                                  color: AppColors.textSub, fontSize: 15)),
                        ],
                      ),
                    )
                  : ListView(
                      children: _results!
                          .map((a) => ArticleListTile(article: a))
                          .toList(),
                    ),
    );
  }
}

// ------------------------------------------------------------------ //
// Tab 3 – Profile (inline)                                            //
// ------------------------------------------------------------------ //
class _ProfileTab extends StatelessWidget {
  const _ProfileTab();

  @override
  Widget build(BuildContext context) {
    return const ProfileScreen();
  }
}


