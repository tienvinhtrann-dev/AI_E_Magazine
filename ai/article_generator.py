"""
AI Article Generator - Simplified Version
Crawl → Tổng hợp → Viết lại → Sinh bài báo mới
"""
import requests
from bs4 import BeautifulSoup
import random
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re
try:
    from groq import Groq
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("⚠️ Groq không được cài đặt. Chạy: pip install groq")


class SimpleArticleGenerator:
    """
    Generator đơn giản để tạo bài báo từ dữ liệu crawl
    """
    
    def __init__(self, api_key=None):
        # Cấu hình Groq API
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        if self.api_key and AI_AVAILABLE:
            self.client = Groq(api_key=self.api_key)
            self.model_name = 'llama-3.1-8b-instant'  # Model tối ưu tránh Rate Limit
            self.use_ai_rewrite = True
            print(f"✅ Groq API đã được kích hoạt - Model: {self.model_name}")
        else:
            self.use_ai_rewrite = False
            print("⚠️ Groq API chưa được cấu hình - Sử dụng tổng hợp đơn giản")
        
        self.sources = {
            'vnexpress': {
                'name': 'VnExpress',
                'search_url': 'https://timkiem.vnexpress.net/?q={keyword}',
                'base_url': 'https://vnexpress.net'
            },
            'tuoitre': {
                'name': 'Tuổi Trẻ',
                'search_url': 'https://tuoitre.vn/tim-kiem.htm?keywords={keyword}',
                'base_url': 'https://tuoitre.vn'
            },
            'thanhnien': {
                'name': 'Thanh Niên',
                'search_url': 'https://thanhnien.vn/tim-kiem/?keywords={keyword}',
                'base_url': 'https://thanhnien.vn'
            }
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Cache URL toàn cục để không crawl/dùng lại bài đã lấy
        self._crawled_urls_cache = set()
        self.last_error = None
        self.max_source_age_hours = None  # Không giới hạn thời gian - lấy bài mới nhất tìm được

    def clear_crawled_cache(self):
        """Xóa cache URL crawl toàn cục để chuẩn bị cho lượt tạo bài mới."""
        self._crawled_urls_cache = set()


    def _clear_last_error(self):
        self.last_error = None

    def _set_last_error(self, message):
        self.last_error = message

    def _parse_datetime_value(self, raw_value):
        if not raw_value:
            return None

        value = str(raw_value).strip()
        if not value:
            return None

        normalized = value.replace('Z', '+00:00')
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass

        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass

        for fmt in (
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%d/%m/%Y %H:%M',
            '%Y-%m-%d',
        ):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None

    def _extract_datetime_from_jsonld(self, payload):
        if isinstance(payload, list):
            for item in payload:
                parsed = self._extract_datetime_from_jsonld(item)
                if parsed:
                    return parsed
            return None

        if not isinstance(payload, dict):
            return None

        for key in ('datePublished', 'dateCreated', 'dateModified', 'uploadDate'):
            parsed = self._parse_datetime_value(payload.get(key))
            if parsed:
                return parsed

        for nested_key in ('@graph', 'mainEntity', 'itemListElement'):
            parsed = self._extract_datetime_from_jsonld(payload.get(nested_key))
            if parsed:
                return parsed

        return None

    def _extract_published_at(self, soup):
        meta_candidates = [
            ('property', 'article:published_time'),
            ('property', 'article:modified_time'),
            ('property', 'og:updated_time'),
            ('name', 'pubdate'),
            ('name', 'publishdate'),
            ('name', 'date'),
            ('itemprop', 'datePublished'),
            ('itemprop', 'dateModified'),
        ]

        for attr_name, attr_value in meta_candidates:
            tag = soup.find('meta', attrs={attr_name: attr_value})
            if not tag:
                continue
            parsed = self._parse_datetime_value(tag.get('content'))
            if parsed:
                return parsed

        for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
            raw_json = (script.string or script.get_text() or '').strip()
            if not raw_json:
                continue
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError:
                continue
            parsed = self._extract_datetime_from_jsonld(payload)
            if parsed:
                return parsed

        return None

    def _is_recent_enough(self, published_at):
        """Không còn giới hạn 72h - chấp nhận mọi bài có thời gian xuất bản hợp lệ."""
        if not published_at:
            return False
        # Chấp nhận mọi bài miễn là có published_at hợp lệ (không giới hạn tuổi bài)
        return True
    
    
    def search_google_news(self, keywords, description='', max_results=15):
        """
        Tìm kiếm bài báo trên Google News để lấy candidate mới nhất.
        Không giới hạn thời gian - lấy bài đầu tiên tìm được phù hợp với từ khóa.
        
        Args:
            keywords: Từ khóa tìm kiếm
            description: Mô tả để tìm kiếm chính xác hơn
            max_results: Số kết quả tối đa
            
        Returns:
            List[str]: Danh sách URLs
        """
        # Query = "Danh mục + Từ khóa" được truyền từ caller (không mix description)
        search_query = (keywords or '').strip()

        print(f"\n🔍 Searching Google for: {search_query}")
        
        try:
            from urllib.parse import quote_plus, unquote, urlparse, parse_qs

            # Google News search — lấy pool đủ rộng, ưu tiên bài mới nhất.
            encoded_query = quote_plus(search_query)
            search_url = f"https://www.google.com/search?q={encoded_query}&tbm=nws&num=30&tbs=qdr:w"
            print(f"📡 URL: {search_url}")
            
            # Giảm timeout để tránh treo lâu nếu mạng yếu / bị chặn Google
            response = requests.get(search_url, headers=self.headers, timeout=7)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tìm các link tin tức với nhiều phương pháp
            urls = []
            seen_urls = set()
            
            # Chỉ lấy từ 6 báo lớn được chấp nhận
            valid_domains = [
                'vnexpress.net', 'tuoitre.vn', 'thanhnien.vn', 'dantri.com.vn',
                'zingnews.vn', 'vietnamnet.vn'
            ]

            def _add_url(candidate):
                if not candidate or not isinstance(candidate, str):
                    return
                if not candidate.startswith('http'):
                    return
                if not any(domain in candidate for domain in valid_domains):
                    return
                if candidate in seen_urls:
                    return
                urls.append(candidate)
                seen_urls.add(candidate)
                print(f"  ✓ Found: {candidate[:60]}...")

            # Method 1: Google News links
            for link in soup.find_all('a'):
                href = link.get('href', '')

                try:
                    if href.startswith('/url?'):
                        parsed = urlparse(href)
                        query_map = parse_qs(parsed.query)
                        candidate = ''
                        if 'q' in query_map and query_map['q']:
                            candidate = unquote(query_map['q'][0])
                        elif 'url' in query_map and query_map['url']:
                            candidate = unquote(query_map['url'][0])
                        _add_url(candidate)
                    elif href.startswith('http'):
                        _add_url(href)

                    if len(urls) >= max_results:
                        break
                except Exception:
                    continue
            
            print(f"✅ Found {len(urls)} unique news URLs (lấy bài mới nhất tìm được)")

            # Nếu không đủ, thử thêm từ direct links
            if len(urls) < 5:
                print("⚠️ Not enough URLs from Google, trying direct links...")
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    _add_url(href)
                    if len(urls) >= max_results:
                        break
            
            time.sleep(1)  # Tránh bị block
            return urls
            
        except Exception as e:
            print(f"⚠️ Google search failed: {e}")
            return []
    
    
    def crawl_articles(self, keywords, description='', max_articles=5):
        """
        Crawl bài báo từ Google Search (tin tức 24h)
        
        Args:
            keywords: Từ khóa tìm kiếm
            description: Mô tả chủ đề
            max_articles: Số bài tối thiểu (mặc định 5)
        
        Returns:
            List[dict]: Danh sách bài báo crawled
        """
        print(f"\n🕷️  Crawling articles with keywords: {keywords}")
        if description:
            print(f"📝 Description: {description}")
        print("=" * 70)
        
        articles = []
        min_sources = max(5, max_articles)  # Tối thiểu 5 nguồn
        
        # Bước 1: Tìm kiếm trên Google (tin 24h) với description
        urls = self.search_google_news(keywords, description, min_sources * 3)
        
        # Bước 2: Crawl nội dung từ các URLs (đảm bảo tối thiểu 5 nguồn)
        if urls:
            print(f"\n📥 Starting to crawl {len(urls)} URLs...")
            print(f"Target: {min_sources} articles from different sources")
            
            for idx, url in enumerate(urls, 1):
                if len(articles) >= min_sources:
                    print(f"✅ Reached target: {len(articles)}/{min_sources} articles")
                    break

                url_str = (url or '').strip()
                if url_str in self._crawled_urls_cache:
                    print(f"  [SKIP-DEDUP] URL already fetched: {url_str[:60]}...")
                    continue
                    
                print(f"\n[{idx}/{len(urls)}] Trying: {url[:70]}...")
                try:
                    article = self._crawl_article_content(url)
                    if article:
                        self._crawled_urls_cache.add(url_str)
                        articles.append(article)
                        print(f"✓ SUCCESS [{len(articles)}/{min_sources}] {article['source']}: {article['title'][:50]}...")
                        time.sleep(0.8)  # Delay lâu hơn để tránh block
                    else:
                        print(f"✗ SKIP: No content extracted")
                except Exception as e:
                    print(f"✗ ERROR: {str(e)[:100]}")
        
        # Bước 3: Nếu vẫn chưa đủ, crawl thêm từ VnExpress
        if len(articles) < min_sources:
            print(f"\n⚠️ Chỉ có {len(articles)}/{min_sources} bài. Crawl thêm từ VnExpress...")
            try:
                needed = min_sources - len(articles)
                vnexpress_articles = self._crawl_vnexpress(keywords, needed)
                articles.extend(vnexpress_articles)
                print(f"✓ Đã thêm {len(vnexpress_articles)} bài từ VnExpress")
            except Exception as e:
                print(f"⚠️ VnExpress crawl failed: {e}")
        
        print(f"\n✅ Total articles crawled: {len(articles)} (minimum: {min_sources})")
        if len(articles) < min_sources:
            print(f"⚠️ Warning: Only got {len(articles)} sources, need {min_sources}")
        return articles
    
    
    def _crawl_article_content(self, url):
        """
        Crawl nội dung từ một URL bất kỳ
        """
        try:
            print(f"  → Fetching: {url[:60]}...")
            response = requests.get(url, headers=self.headers, timeout=7)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')

            published_at = self._extract_published_at(soup)
            if not published_at:
                # Nếu không parse được thời gian, vẫn cho qua (không bỏ bài)
                print("  ⚠ Missing published time metadata, but continuing (no time filter)...")
            else:
                print(f"  → Published at: {published_at.isoformat()}")
            
            # Xác định source
            # Chỉ crawl từ 6 nguồn báo lớn được chấp nhận
            allowed_domains = {
                'vnexpress.net': 'VnExpress',
                'tuoitre.vn': 'Tuổi Trẻ',
                'thanhnien.vn': 'Thanh Niên',
                'dantri.com.vn': 'Dân Trí',
                'zingnews.vn': 'Zing News',
                'vietnamnet.vn': 'VietnamNet',
            }

            if not any(d in url for d in allowed_domains.keys()):
                print(f"  ✗ Domain not in allowed list, skipping")
                return None

            source_map = allowed_domains
            
            source = 'Unknown'
            for domain, name in source_map.items():
                if domain in url:
                    source = name
                    break
            
            print(f"  → Source: {source}")
            
            # Lấy title (các selector phổ biến)
            title = None
            title_selectors = [
                'h1.title-detail', 
                'h1.article-title',
                'h1.detail-title',
                'h1.title-post',
                '.article-title h1',
                'h1',
                'title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and len(title) > 10:  # Đảm bảo title có ý nghĩa
                        print(f"  → Title found: {title[:60]}...")
                        break
            
            if not title:
                print(f"  ✗ No title found, skipping...")
                return None
            
            # Lấy content (các selector phổ biến cho nhiều trang)
            content_parts = []
            content_selectors = [
                'article.fck_detail',  # VnExpress
                '.article-content',    # Tuổi Trẻ, Thanh Niên
                'article',             # Generic
                '.content-detail',     # Dân Trí
                '.detail-content',     # VietnamNet
                '.kbwc-content',       # Zing News
                '.the-article-body'    # Soha
            ]
            
            content_found = False
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    paragraphs = content_elem.find_all(['p', 'h2', 'h3'])
                    for elem in paragraphs[:25]:  # Lấy 25 elements (tăng từ 20)
                        text = elem.get_text(strip=True)
                        if len(text) > 50:
                            content_parts.append(text)
                    if content_parts:
                        content_found = True
                        print(f"  → Content found: {len(content_parts)} paragraphs using {selector}")
                        break
            
            # Nếu không tìm thấy, thử lấy tất cả <p> trong body
            if not content_found:
                print(f"  → Trying fallback: all <p> tags...")
                for p in soup.find_all('p')[:20]:
                    text = p.get_text(strip=True)
                    if len(text) > 50:
                        content_parts.append(text)
                if content_parts:
                    print(f"  → Fallback success: {len(content_parts)} paragraphs")
            
            content = '\n\n'.join(content_parts)
            
            if not content or len(content) < 200:
                print(f"  ✗ Content too short ({len(content)} chars), skipping...")
                return None
            
            print(f"  ✓ Content length: {len(content)} chars")
            
            # Lấy description (meta tag)
            description = ""
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content', '')
            
            # Lấy tất cả hình ảnh trong bài viết (lấy nhiều ảnh)
            images = []
            # Thử lấy ảnh og:image đầu tiên
            og_img = soup.select_one('meta[property="og:image"]')
            if og_img:
                img_url = og_img.get('content')
                if img_url and img_url.startswith('http'):
                    images.append({'url': img_url, 'source': source, 'caption': title})
            
            # Lấy thêm ảnh trong content
            content_selectors = ['article.fck_detail img', '.article-content img', 'article img', '.detail-content img', '.kbwc-content img']
            for selector in content_selectors:
                for img_elem in soup.select(selector)[:5]:  # Lấy tối đa 5 ảnh từ mỗi selector
                    img_url = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-original')
                    
                    # Đảm bảo URL đầy đủ
                    if img_url and not img_url.startswith('http'):
                        from urllib.parse import urljoin
                        img_url = urljoin(url, img_url)
                    
                    # Lọc ảnh hợp lệ
                    if img_url and img_url.startswith('http') and not any(skip in img_url.lower() for skip in ['logo', 'icon', 'avatar', 'banner', 'ads']):
                        # Lấy caption nếu có
                        caption = img_elem.get('alt') or img_elem.get('title') or ''
                        if len(images) < 5:  # Tối đa 5 ảnh/bài
                            images.append({'url': img_url, 'source': source, 'caption': caption or title})
                
                if images:
                    break
            
            if title and content:
                return {
                    'title': title,
                    'url': url,
                    'source': source,
                    'published_at': published_at.isoformat(),
                    'content': content,
                    'description': description,
                    'image_url': images[0]['url'] if images else None,
                    'images': images  # Lưu tất cả ảnh với source
                }
            
            return None
            
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            return None
    
    def _detect_vnexpress_category_url(self, topic_or_desc):
        """Thử nhận diện URL danh mục VnExpress từ tên/miêu tả danh mục.

        Hỗ trợ các trường hợp:
        - Người dùng nhập thẳng URL: https://vnexpress.net/the-thao
        - Người dùng nhập slug: "the-thao", "kinh-doanh"...
        - Người dùng nhập tên danh mục có dấu: "Thể thao", "Kinh doanh"...
        """
        raw = (topic_or_desc or "").strip()
        if not raw:
            return None

        # Nếu đã là URL VnExpress thì dùng luôn
        if "vnexpress.net" in raw:
            return raw

        text = raw.lower().strip()

        # Nếu trông giống slug (không khoảng trắng, có gạch ngang) thì build URL
        if " " not in text and "-" in text:
            return f"https://vnexpress.net/{text.strip('/')}"

        # Map một số tên danh mục phổ biến sang URL cố định
        mappings = [
            ("thời sự", "https://vnexpress.net/thoi-su"),
            ("thoi su", "https://vnexpress.net/thoi-su"),
            ("thế giới", "https://vnexpress.net/the-gioi"),
            ("the gioi", "https://vnexpress.net/the-gioi"),
            ("kinh doanh", "https://vnexpress.net/kinh-doanh"),
            ("khoa học công nghệ", "https://vnexpress.net/khoa-hoc-cong-nghe"),
            ("khoa hoc cong nghe", "https://vnexpress.net/khoa-hoc-cong-nghe"),
            ("thể thao", "https://vnexpress.net/the-thao"),
            ("the thao", "https://vnexpress.net/the-thao"),
            ("giải trí", "https://vnexpress.net/giai-tri"),
            ("giai tri", "https://vnexpress.net/giai-tri"),
            ("pháp luật", "https://vnexpress.net/phap-luat"),
            ("phap luat", "https://vnexpress.net/phap-luat"),
            ("giáo dục", "https://vnexpress.net/giao-duc"),
            ("giao duc", "https://vnexpress.net/giao-duc"),
            ("đời sống", "https://vnexpress.net/doi-song"),
            ("doi song", "https://vnexpress.net/doi-song"),
            ("sức khỏe", "https://vnexpress.net/suc-khoe"),
            ("suc khoe", "https://vnexpress.net/suc-khoe"),
            ("du lịch", "https://vnexpress.net/du-lich"),
            ("du lich", "https://vnexpress.net/du-lich"),
            # Một số danh mục con mà bạn đang dùng: Chính Trị, Bóng Đá, Giá Vàng
            ("chính trị", "https://vnexpress.net/thoi-su/chinh-tri"),
            ("chinh tri", "https://vnexpress.net/thoi-su/chinh-tri"),
            ("bóng đá", "https://vnexpress.net/the-thao/bong-da"),
            ("bong da", "https://vnexpress.net/the-thao/bong-da"),
            ("giá vàng", "https://vnexpress.net/kinh-doanh/vang-tien-te"),
            ("gia vang", "https://vnexpress.net/kinh-doanh/vang-tien-te"),
        ]

        for key, url in mappings:
            if key in text:
                return url

        return None

    def _crawl_vnexpress_category(self, category_spec, max_articles=6):
        """Crawl bài viết trực tiếp từ một danh mục VnExpress (lấy luôn ảnh).

        category_spec có thể là:
        - URL đầy đủ của danh mục (https://vnexpress.net/the-thao)
        - slug (the-thao, kinh-doanh,...)
        - tên danh mục (Thể thao, Kinh doanh, ...), sẽ được map sang URL.
        """
        from urllib.parse import urljoin

        url = self._detect_vnexpress_category_url(category_spec)
        if not url:
            print(f"[VNEXP-CAT] Không nhận diện được URL danh mục từ: {category_spec!r}")
            return []

        print(f"[VNEXP-CAT] Crawling category: {url}")
        articles = []

        try:
            resp = requests.get(url, headers=self.headers, timeout=7)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            # Chấp nhận nhiều dạng URL bài viết, không chỉ dạng "-ID.html"
            article_pattern = re.compile(r"^https?://vnexpress\.net/[^?#]+$")
            links = []
            seen = set()

            # Ưu tiên các thẻ tiêu đề bài viết trên trang danh mục
            selectors = [
                "h3.title-news a[href]",
                "article a[href]",
                "h2 a[href]",
            ]

            for selector in selectors:
                for a in soup.select(selector):
                    href = (a.get("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("//"):
                        href = "https:" + href
                    elif href.startswith("/"):
                        href = urljoin("https://vnexpress.net", href)

                    if not article_pattern.match(href):
                        continue
                    if href in seen:
                        continue
                    seen.add(href)
                    links.append(href)
                    if len(links) >= max_articles:
                        break
                if len(links) >= max_articles:
                    break

            print(f"[VNEXP-CAT] Found {len(links)} article links from category")

            for link in links:
                try:
                    art = self._crawl_article_content(link)
                    if art:
                        articles.append(art)
                        print(f"   [+CAT] {art['title'][:70]}")
                    if len(articles) >= max_articles:
                        break
                except Exception as e:
                    print(f"   [VNEXP-CAT] Error crawling article: {str(e)[:80]}")
                    continue

        except Exception as e:
            print(f"[VNEXP-CAT] Error fetching category page: {str(e)[:80]}")

        return articles

    def _crawl_vnexpress(self, keywords, max_articles, skip_urls=None):
        """Crawl bài viết từ trang tìm kiếm VnExpress (tim-kiem).

        - `keywords`: Chuỗi tìm kiếm, ví dụ "món ngon Đà Lạt".
        - Luôn ưu tiên thứ tự bài giống trang search.
        - `skip_urls`: tập URL cần bỏ qua (đã dùng cho các bài trước).
        """
        from urllib.parse import quote_plus, urljoin

        if skip_urls is None:
            skip_urls = set()
        else:
            skip_urls = {str(u).strip() for u in skip_urls if isinstance(u, str)}

        articles = []

        try:
            query = str(keywords or "").strip()
            if not query:
                return []

            # Dùng đúng trang tìm kiếm timkiem.vnexpress.net giống bạn đang sử dụng
            # Ví dụ: https://timkiem.vnexpress.net/?search_q=món%20ngon%20Đà%20Lạt&cate_code=&media_type=all&latest=1&fromdate=&todate=&date_format=all
            search_url = (
                "https://timkiem.vnexpress.net/?search_q="
                + quote_plus(query)
                + "&cate_code=&media_type=all&latest=1&fromdate=&todate=&date_format=all"
            )
            print(f"📡 Searching VnExpress (timkiem): {search_url}")

            resp = requests.get(search_url, headers=self.headers, timeout=7)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            # Chấp nhận mọi URL bài viết hợp lệ trên VnExpress (không giới hạn '-ID.html')
            article_pattern = re.compile(r"^https?://vnexpress\.net/[^?#]+$")
            links = []  # mỗi phần tử: {url, title, description}
            seen = set()

            selectors = [
                "h3.title_news a[href]",  # timkiem.vnexpress.net dùng title_news
                "h3.title-news a[href]",
                "article a[href]",
                "h2 a[href]",
            ]

            for selector in selectors:
                for a in soup.select(selector):
                    href = (a.get("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("//"):
                        href = "https:" + href
                    elif href.startswith("/"):
                        href = urljoin("https://vnexpress.net", href)

                    href = href.split("#")[0]
                    if not article_pattern.match(href):
                        continue
                    if href in seen:
                        continue
                    seen.add(href)

                    # Lấy tiêu đề & mô tả tóm tắt ngay trên trang search,
                    # dùng làm nguồn dữ liệu tối thiểu nếu crawl chi tiết lỗi.
                    title_text = a.get_text(strip=True) or ""
                    desc_text = ""
                    h3 = a.find_parent("h3")
                    if h3:
                        # Trên timkiem.vnexpress.net mô tả thường nằm trong <p> kế bên
                        desc_p = h3.find_next_sibling("p")
                        if desc_p:
                            desc_text = desc_p.get_text(" ", strip=True)

                    links.append({
                        "url": href,
                        "title": title_text,
                        "description": desc_text,
                    })
                    if len(links) >= max_articles * 2:
                        break
                if len(links) >= max_articles * 2:
                    break

            print(f"[VNEXP-SEARCH] Found {len(links)} candidate links")

            for item in links:
                link = item["url"]
                if len(articles) >= max_articles:
                    break
                if link in skip_urls:
                    print(f"   [SKIP] Already used URL: {link[:80]}")
                    continue
                try:
                    # Crawl bài chi tiết thành công (không còn giới hạn 72h).
                    art = self._crawl_article_content(link)
                    if art:
                        articles.append(art)
                        print(f"   [+SEARCH] {art['title'][:70]}")
                except Exception as e:
                    print(f"   [VNEXP-SEARCH] Error crawling article: {str(e)[:80]}")
                    continue

        except Exception as e:
            print(f"❌ VnExpress search error: {e}")

        return articles

    def _crawl_rss_multisource(self, topic, keywords, max_articles=6, keyword_filter=True):
        """Crawl RSS từ nhiều báo để đảm bảo dữ liệu đa nguồn"""
        feeds = [
            ('VnExpress', 'https://vnexpress.net/rss/du-lich.rss'),
            ('VnExpress', 'https://vnexpress.net/rss/doi-song.rss'),
            ('Tuổi Trẻ', 'https://tuoitre.vn/rss/du-lich.rss'),
            ('Tuổi Trẻ', 'https://tuoitre.vn/rss/nhip-song-tre.rss'),
            ('Thanh Niên', 'https://thanhnien.vn/rss/du-lich.rss'),
            ('Thanh Niên', 'https://thanhnien.vn/rss/doi-song.rss'),
            ('Dân Trí', 'https://dantri.com.vn/rss/du-lich.rss'),
            ('VietnamNet', 'https://vietnamnet.vn/rss/du-lich.rss'),
        ]

        query_tokens = set()
        for chunk in [str(topic or ''), str(keywords or '')]:
            for token in re.split(r'[,\s]+', chunk.lower()):
                token = token.strip()
                if len(token) >= 3:
                    query_tokens.add(token)

        collected = []
        seen_urls = set()
        used_source_domains = set()

        for feed_source, feed_url in feeds:
            if len(collected) >= max_articles:
                break
            try:
                print(f"  [RSS] Fetching {feed_source}: {feed_url}")
                resp = requests.get(feed_url, headers=self.headers, timeout=7)
                soup = BeautifulSoup(resp.text, 'xml')
                items = soup.find_all('item')[:12]

                for item in items:
                    if len(collected) >= max_articles:
                        break
                    link_tag = item.find('link')
                    title_tag = item.find('title')
                    desc_tag = item.find('description')
                    if not link_tag:
                        continue

                    url = (link_tag.text or '').strip()
                    if not url or url in seen_urls:
                        continue

                    title_text = (title_tag.text or '').strip() if title_tag else ''
                    desc_text = (desc_tag.text or '').strip() if desc_tag else ''
                    combined = f"{title_text} {desc_text}".lower()
                    if keyword_filter and query_tokens and not any(t in combined for t in query_tokens):
                        continue

                    article = self._crawl_article_content(url)
                    if not article:
                        continue

                    normalized_source = (article.get('source') or feed_source or '').strip().lower()
                    # Ưu tiên đa nguồn: mỗi nguồn lấy trước 1 bài, sau đó mới lấy thêm
                    if normalized_source in used_source_domains and len(used_source_domains) < 3 and len(collected) < max_articles:
                        continue

                    seen_urls.add(url)
                    collected.append(article)
                    if normalized_source:
                        used_source_domains.add(normalized_source)
                    print(f"    [+RSS] {article.get('source', feed_source)}: {article.get('title', '')[:60]}")
                    time.sleep(0.4)
            except Exception as e:
                print(f"  [RSS-WARN] {feed_source}: {str(e)[:80]}")
                continue

        return collected

    def _build_sources_brief(self, crawled_articles, max_items=6):
        """Tạo tóm tắt nguồn để ép AI viết dựa trên dữ liệu thật"""
        if not crawled_articles:
            return ""

        lines = []
        for idx, article in enumerate(crawled_articles[:max_items], 1):
            source = article.get('source', 'Nguồn không rõ')
            title = (article.get('title') or '').strip()
            url = (article.get('url') or '').strip()
            content = re.sub(r'\s+', ' ', (article.get('content') or '').strip())
            snippet = content[:260]
            lines.append(
                f"[S{idx}] {source}\n"
                f"Tiêu đề: {title}\n"
                f"URL: {url}\n"
                f"Dữ kiện chính: {snippet}"
            )

        return "\n\n".join(lines)

    def _keyword_list(self, keywords):
        raw = str(keywords or '').strip().lower()
        if not raw:
            return []

        parts = [p.strip() for p in re.split(r'[,;\n]+', raw) if p.strip()]
        if len(parts) == 1:
            parts = [p.strip() for p in re.split(r'\s{2,}|\s*,\s*', raw) if p.strip()]
            if not parts:
                parts = [raw]

        uniq = []
        seen = set()
        for p in parts:
            p = re.sub(r'\s+', ' ', p).strip()
            if len(p) < 2:
                continue
            if p in seen:
                continue
            seen.add(p)
            uniq.append(p)
        return uniq[:12]

    def _topic_tokens(self, topic):
        tokens = []
        for tk in re.split(r'[\s,;:/|\\-]+', str(topic or '').lower()):
            tk = tk.strip()
            if len(tk) >= 3:
                tokens.append(tk)
        return list(dict.fromkeys(tokens))

    def _heuristic_alignment_agent(self, topic, keywords, article, agent_name='heuristic-core', min_keyword_ratio=0.35):
        title = str(article.get('title') or '')
        summary = str(article.get('summary') or '')
        content = str(article.get('content') or '')
        text = f"{title}\n{summary}\n{content[:8000]}".lower()

        topic_tokens = self._topic_tokens(topic)
        topic_hit = any(t in text for t in topic_tokens) if topic_tokens else True

        keyword_list = self._keyword_list(keywords)
        if keyword_list:
            keyword_hits = [kw for kw in keyword_list if kw in text]
            kw_ratio = len(keyword_hits) / max(len(keyword_list), 1)
        else:
            keyword_hits = []
            kw_ratio = 1.0

        score = 0
        score += 45 if topic_hit else 0
        score += min(45, int(kw_ratio * 45))
        if len(content) >= 800:
            score += 10

        passed = topic_hit and (kw_ratio >= min_keyword_ratio)
        if not keyword_list:
            passed = topic_hit

        rationale = (
            f"topic_hit={topic_hit}, keyword_hits={len(keyword_hits)}/{len(keyword_list) if keyword_list else 0}, "
            f"keyword_ratio={kw_ratio:.2f}"
        )
        return {
            'agent': agent_name,
            'score': max(0, min(100, int(score))),
            'pass': bool(passed),
            'rationale': rationale,
            'missing_keywords': [kw for kw in keyword_list if kw not in keyword_hits][:5],
        }

    def _llm_alignment_agent(self, agent_name, agent_focus, topic, keywords, article):
        if not self.use_ai_rewrite or not hasattr(self, 'client') or self.client is None:
            return None

        title = str(article.get('title') or '')
        summary = str(article.get('summary') or '')
        content = str(article.get('content') or '')

        prompt = f"""Bạn là agent kiểm duyệt nội dung: {agent_name}.
Mục tiêu: {agent_focus}.

Hãy kiểm tra bài viết AI có bám đúng danh mục và từ khóa không.

Danh mục: {topic}
Từ khóa người dùng: {keywords}

Tiêu đề: {title}
Tóm tắt: {summary}
Nội dung (rút gọn): {content[:3500]}

Trả về DUY NHẤT 1 JSON hợp lệ theo schema:
{{
  "score": 0-100,
  "pass": true/false,
  "rationale": "<toi da 180 ky tu>",
  "missing_keywords": ["..."]
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        'role': 'system',
                        'content': 'Bạn là agent kiểm duyệt chất lượng nội dung. Luôn trả về JSON hợp lệ, không thêm văn bản ngoài JSON.'
                    },
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=260,
                top_p=0.9,
            )
            raw = (response.choices[0].message.content or '').strip()
            m = re.search(r'\{[\s\S]*\}', raw)
            payload = json.loads(m.group(0) if m else raw)
            score = int(payload.get('score', 0))
            passed = payload.get('pass', score >= 70)
            if isinstance(passed, str):
                passed = passed.strip().lower() == 'true'
            rationale = str(payload.get('rationale', '')).strip()[:180]
            missing = payload.get('missing_keywords', [])
            if not isinstance(missing, list):
                missing = []
            return {
                'agent': agent_name,
                'score': max(0, min(100, score)),
                'pass': bool(passed),
                'rationale': rationale or 'No rationale',
                'missing_keywords': [str(x).strip() for x in missing if str(x).strip()][:5],
            }
        except Exception as e:
            print(f"[REVIEW-WARN] {agent_name} failed: {e}")
            return {
                'agent': agent_name,
                'score': 0,
                'pass': False,
                'rationale': 'AI reviewer error',
                'missing_keywords': [],
            }

    def _run_multi_agent_alignment_review(self, topic, keywords, article):
        agents = []

        agents.append(
            self._heuristic_alignment_agent(
                topic=topic,
                keywords=keywords,
                article=article,
                agent_name='heuristic-core',
                min_keyword_ratio=0.35,
            )
        )

        if self.use_ai_rewrite and hasattr(self, 'client') and self.client is not None:
            reviewer_1 = self._llm_alignment_agent(
                agent_name='reviewer-topic-fit',
                agent_focus='Độ bám sát danh mục/chủ đề chính',
                topic=topic,
                keywords=keywords,
                article=article,
            )
            reviewer_2 = self._llm_alignment_agent(
                agent_name='reviewer-keyword-fit',
                agent_focus='Độ bao phủ từ khóa người dùng và tính liên quan ngữ cảnh',
                topic=topic,
                keywords=keywords,
                article=article,
            )
            if reviewer_1:
                agents.append(reviewer_1)
            if reviewer_2:
                agents.append(reviewer_2)
        else:
            agents.append(
                self._heuristic_alignment_agent(
                    topic=topic,
                    keywords=keywords,
                    article=article,
                    agent_name='heuristic-strict-keyword',
                    min_keyword_ratio=0.50,
                )
            )
            agents.append(
                self._heuristic_alignment_agent(
                    topic=topic,
                    keywords=keywords,
                    article=article,
                    agent_name='heuristic-topic-guard',
                    min_keyword_ratio=0.20,
                )
            )

        if not agents:
            return {'pass': False, 'average_score': 0, 'pass_count': 0, 'agents': []}

        pass_count = sum(1 for a in agents if a.get('pass'))
        avg_score = sum(int(a.get('score', 0)) for a in agents) / max(len(agents), 1)
        overall_pass = pass_count >= 2 and avg_score >= 65
        failed_reasons = [a.get('rationale', '') for a in agents if not a.get('pass') and a.get('rationale')]

        return {
            'pass': bool(overall_pass),
            'average_score': round(avg_score, 2),
            'pass_count': pass_count,
            'agents': agents,
            'failed_reasons': failed_reasons[:3],
        }

    def _validate_generated_article_alignment(self, topic, keywords, article):
        review = self._run_multi_agent_alignment_review(topic, keywords, article)
        article['alignment_review'] = review

        if review.get('pass'):
            print(f"[REVIEW] PASS avg={review.get('average_score')} pass_count={review.get('pass_count')}")
            return True

        reason = ''
        if review.get('failed_reasons'):
            reason = f" ({review['failed_reasons'][0]})"
        message = (
            "Nội dung AI viết lại chưa bám sát danh mục/từ khóa. "
            "Vui lòng nhập lại từ khóa cụ thể hơn để tạo lại bài."
        )
        self._set_last_error(message + reason)
        print(f"[REVIEW] FAIL avg={review.get('average_score')} pass_count={review.get('pass_count')}{reason}")
        return False
    
    def _validate_and_sanitize_forbidden_keywords(self, article, forbidden_keywords):
        """
        Kiểm tra và loại bỏ từ khóa cấm bằng cách yêu cầu LLM viết lại (tối đa 3 lần).
        """
        if not forbidden_keywords or not article:
            return article

        violation_count = 0
        max_attempts = 3
        current_article = article

        while violation_count < max_attempts:
            # 1. Tìm các từ cấm bị vi phạm (case-insensitive)
            title = current_article.get("title", "")
            summary = current_article.get("summary", "")
            content = current_article.get("content", "")

            # Combine all text to search
            combined_text = f"{title}\n{summary}\n{content}".lower()

            violated_words = []
            for kw in forbidden_keywords:
                kw_lower = kw.lower()
                if kw_lower in combined_text:
                    violated_words.append(kw)

            if not violated_words:
                # Không vi phạm, trả về bài viết
                if violation_count > 0:
                    print(f"✨ Article successfully sanitized on attempt {violation_count}!")
                return current_article

            violation_count += 1
            print(f"⚠️ Phát hiện vi phạm từ khóa cấm (lần {violation_count}/{max_attempts}): {violated_words}")
            
            if violation_count >= max_attempts:
                # Vượt quá số lần thử, dừng và đặt lỗi
                err_msg = f"Nội dung vi phạm các từ khóa cấm: {', '.join(violated_words)} (Đã thử viết lại {max_attempts} lần không thành công)."
                self._set_last_error(err_msg)
                print(f"❌ Safety check failed: {err_msg}")
                return None

            # 2. Gọi LLM viết lại bài viết để sửa đổi các từ cấm
            rewritten_article = self._rewrite_to_fix_violations(current_article, violated_words)
            if not rewritten_article:
                err_msg = "Không thể viết lại bài viết để sửa đổi từ khóa cấm."
                self._set_last_error(err_msg)
                return None
            
            current_article = current_article.copy()
            current_article["title"] = rewritten_article.get("title", current_article["title"])
            current_article["summary"] = rewritten_article.get("summary", current_article["summary"])
            current_article["content"] = rewritten_article.get("content", current_article["content"])

        return None

    def _rewrite_to_fix_violations(self, article, violated_keywords):
        """
        Gọi LLM để viết lại title, summary, và content loại bỏ/thay thế các từ cấm.
        """
        if not self.use_ai_rewrite or not self.client:
            return None

        kw_str = ", ".join(violated_keywords)
        prompt = f"""Bạn là một chuyên gia hiệu đính và biên tập nội dung.
Bài viết sau đây đã vi phạm chính sách an toàn do chứa các từ khóa cấm: [{kw_str}].

Nhiệm vụ của bạn:
1. Hãy viết lại tiêu đề (title), tóm tắt (summary) và nội dung (content) của bài viết để TUYỆT ĐỐI KHÔNG xuất hiện bất kỳ từ khóa cấm nào nêu trên (kể cả viết hoa hay viết thường).
2. Hãy thay thế các từ cấm bằng các từ đồng nghĩa hoặc diễn đạt lại câu cho tự nhiên, chuyên nghiệp và đúng ngữ cảnh mà không làm mất đi thông tin cốt lõi.
3. Không thay đổi cấu trúc định dạng của nội dung gốc (giữ nguyên 3 đoạn văn xuôi cho content).

Bài viết gốc:
- Tiêu đề: {article.get('title')}
- Tóm tắt: {article.get('summary')}
- Nội dung: {article.get('content')}

Yêu cầu đầu ra:
Bạn bắt buộc phải trả về kết quả ở định dạng JSON thuần túy, không có thẻ markdown ```json, không có text giải thích trước hoặc sau. JSON phải có cấu trúc chính xác như sau:
{{
  "title": "tiêu đề đã sửa đổi",
  "summary": "tóm tắt đã sửa đổi",
  "content": "nội dung đã sửa đổi"
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là chuyên gia sửa đổi văn bản và luôn trả về kết quả định dạng JSON chính xác."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=3000
            )
            raw = response.choices[0].message.content.strip()
            
            # Clean potential markdown wrapping if any
            cleaned_raw = raw
            if cleaned_raw.startswith("```"):
                cleaned_raw = re.sub(r"^```[a-zA-Z]*\n", "", cleaned_raw)
                cleaned_raw = re.sub(r"\n```$", "", cleaned_raw)
            cleaned_raw = cleaned_raw.strip()
            
            parsed = json.loads(cleaned_raw)
            return parsed
        except Exception as e:
            print(f"[WARN] Error in rewrite_to_fix_violations: {e}")
            return None
    
    def generate_article_from_sources(self, topic, description, keywords, crawled_articles, forbidden_keywords=None):
        """
        Tạo bài báo mới từ các bài đã crawl
        
        Args:
            topic: Chủ đề chính
            description: Mô tả ngắn
            keywords: Từ khóa
            crawled_articles: List các bài đã crawl
            forbidden_keywords: Từ khóa cấm
        
        Returns:
            dict: Bài báo mới
        """
        print(f"\n🤖 Generating new article...")
        print("=" * 70)
        
        if not crawled_articles:
            print("❌ No source articles to generate from!")
            return None
        
        # Tạo title mới
        new_title = self._generate_title(topic, crawled_articles)
        
        # Tạo summary
        new_summary = self._generate_summary(description, crawled_articles)
        
        # Tạo content
        new_content = self._generate_content(topic, description, crawled_articles, forbidden_keywords)
        
        # Lấy source URLs
        source_urls = [article['url'] for article in crawled_articles]
        
        # Collect images from articles with source attribution
        all_images = []
        for article in crawled_articles:
            if article.get('images'):
                # Lấy tất cả ảnh từ article (đã có source và caption)
                all_images.extend(article['images'])
            elif article.get('image_url'):
                # Fallback: nếu chỉ có image_url
                all_images.append({
                    'url': article['image_url'],
                    'source': article.get('source', 'Unknown'),
                    'caption': article.get('title', '')
                })

        # Lấy tối đa 15 ảnh để đủ cho 5 phần (mỗi phần 2-3 ảnh)
        selected_images = all_images[:15]

        # Tạo image_urls list đơn giản để tương thích ngược
        image_urls = [img['url'] for img in selected_images]

        # Ảnh đại diện chính cho bài: dùng ảnh đầu tiên nếu có
        main_image_url = image_urls[0] if image_urls else None
        
        result = {
            'title': new_title,
            'summary': new_summary,
            'content': new_content,
            'keywords': keywords,
            'topic': topic,
            'description': description,
            'source_urls': source_urls,
            'image_url': main_image_url,
            'image_urls': image_urls,
            'images_with_source': selected_images,  # Danh sách ảnh kèm nguồn
            'sources_count': len(crawled_articles)
        }
        
        print(f"\n✅ Article generated successfully!")
        print(f"   📝 Title: {new_title}")
        print(f"   📊 Length: {len(new_content)} characters")
        print(f"   📚 Sources: {len(source_urls)}")
        print(f"   🖼️ Images: {len(selected_images)} with source attribution")
        
        return result
    
    
    def _generate_title(self, topic, articles):
        """Tạo tiêu đề mới dạng tóm tắt thay vì template chung chung."""

        # Nếu có article nguồn, ưu tiên dùng lại tiêu đề nguồn đầu tiên
        # (thường đã là câu tóm tắt nội dung chính).
        if articles:
            first_title = (articles[0].get('title') or '').strip()
            if first_title:
                return first_title

        # Fallback: dùng chính topic, không thêm các cụm như
        # "Phân tích chuyên sâu" hay "Những điều bạn cần biết".
        return str(topic) if topic else "Bài viết từ AI"
    
    
    def _generate_summary(self, description, articles):
        """Tạo tóm tắt"""
        if description:
            return f"{description} Bài viết tổng hợp từ {len(articles)} nguồn tin uy tín."
        
        # Lấy description từ bài đầu tiên
        if articles and articles[0].get('description'):
            return articles[0]['description'][:200] + "..."
        
        return "Bài viết tổng hợp thông tin từ nhiều nguồn tin tức."
    
    
    def _rewrite_with_ai(self, original_content, topic, forbidden_keywords=None):
        """
        Viết lại nội dung bằng Gemini AI
        """
        if not self.use_ai_rewrite:
            return original_content
        
        try:
            prompt = f"""Bạn là AI E-Magazine Writer, một biên tập viên báo điện tử chuyên nghiệp của tờ báo hàng đầu Việt Nam.

NHIỆM VỤ: Dựa trên thông tin từ các nguồn tin tức dưới đây về chủ đề "{topic}", hãy viết LẠI phần nội dung bài báo hoàn chỉnh, khách quan, giàu thông tin và mạch lạc.

YÊU CẦU BẮT BUỘC VỀ NỘI DUNG (MỤC TIÊU):
- Bài viết phải khách quan, chính xác, dễ đọc, giàu thông tin, không lặp ý, không suy diễn, không bịa đặt, không thiên vị, và tự nhiên như được viết bởi biên tập viên chuyên nghiệp.
- Tuyệt đối KHÔNG viết giống văn nghị luận học đường. Không dùng các mẫu câu máy móc, không viết kiểu giáo điều/dạy đời/cổ vũ/kết luận thay độc giả.
- CHỈ sử dụng thông tin có thực xuất hiện trong dữ liệu nguồn. Không bổ sung thông tin từ trí nhớ, không tạo số liệu mới, không tạo trích dẫn/phát biểu/địa điểm/thời gian giả mạo.
- Giọng văn: trung lập, khách quan, hiện đại, rõ ràng, súc tích. Không dùng văn phong cảm tính.
- Độ dài: Khoảng 900-1500 từ. Không viết để đủ chữ.
- Cấu trúc nội dung: Bài viết KHÔNG được chia thành các phần/mục/tiêu đề con. TUYỆT ĐỐI KHÔNG sử dụng bất kỳ ký tự tiêu đề phụ nào như #, ##, ###, hoặc các ký tự đánh số như 1., 2., Phần I, Phần II. Bài viết phải được trình bày hoàn toàn dưới dạng các đoạn văn xuôi (khoảng 4-6 đoạn văn dài, mạch lạc) liên kết chặt chẽ với nhau, chuyển ý mượt mà tự nhiên như một bài báo điện tử chuẩn và hay trên VnExpress, Tuổi Trẻ, Thanh Niên. Nội dung đi thẳng vào vấn đề chính, tiếp nối bằng phân tích diễn biến thực tế, bối cảnh liên quan và mở rộng góc nhìn, kết thúc khách quan mà không triết lý sáo rỗng.
- TUYỆT ĐỐI KHÔNG viết các tiêu đề hoặc cụm từ in đậm đứng riêng biệt (như **Bí quyết thành công**, **Tóm lại**, **Kết luận**, **Sự nỗ lực của thủ khoa**...) để làm tiêu đề phụ. KHÔNG ghi các từ in đậm/tóm tắt ý chính ở đầu mỗi đoạn văn. Mỗi đoạn văn phải bắt đầu trực tiếp bằng nội dung diễn đạt chi tiết mà không có nhãn in đậm nào ở đầu dòng.
- Chống lặp ý: Mỗi đoạn chỉ trình bày MỘT ý mới, không nhắc lại ý cũ. Không lặp cấu trúc, câu, từ khóa.
- KHÔNG sử dụng các từ/cụm từ sau: "Có thể thấy", "Điều này cho thấy", "Một trong những", "Không chỉ", "Bên cạnh đó", "Hơn nữa", "Qua đó", "Theo nghiên cứu", "Theo báo cáo", "Tóm lại", "Nhìn chung", "Cuối cùng".
- Ngôn ngữ: Ưu tiên câu ngắn (20-30 từ). Sử dụng động từ mạnh, hạn chế tính từ và trạng từ sáo rỗng.
- Đa dạng câu: Không viết các câu liên tiếp bắt đầu bằng cùng một từ hoặc cấu trúc chủ ngữ giống hệt nhau.

THÔNG TIN TỪ CÁC NGUỒN THAM KHẢO:
{original_content}

---
HÃY VIẾT NỘI DUNG BÀI BÁO HOÀN CHỈNH:"""

            if not hasattr(self, 'client') or self.client is None:
                print("❌ Groq client not initialized!")
                return original_content
                
            print("📡 Calling Groq API...")
            print(f"   - Model: {self.model_name}")
            print(f"   - Prompt length: {len(prompt)} chars")
            
            system_content = "Bạn là một biên tập viên báo điện tử chuyên nghiệp. Nhiệm vụ của bạn là viết lại bài báo với ngôn từ khách quan, trung lập, súc tích, hoàn toàn không lặp ý. TUYỆT ĐỐI KHÔNG sử dụng tiêu đề phụ, heading (như #, ##, ###), chữ in đậm làm tiêu đề phân đoạn, hay số thứ tự phần nào trong bài viết. Bài viết chỉ được phép có các đoạn văn xuôi liên kết mượt mà."
            if forbidden_keywords:
                kw_str = ", ".join(forbidden_keywords)
                system_content += f" Đặc biệt, Tuyệt đối KHÔNG được sử dụng bất kỳ từ hoặc cụm từ cấm nào sau đây trong bài viết: {kw_str}."

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            rewritten = response.choices[0].message.content.strip()

            # Làm sạch: loại bỏ heading markdown và các cụm tiêu đề không mong muốn
            import re as _re
            banned_starts = [
                "ứng dụng thực tiễn",
                "tầm quan trọng của",
                "góc nhìn chiến lược",
                "khuyến nghị cho người đọc",
            ]

            lines = rewritten.split('\n')
            cleaned_blocks = []
            buffer = []

            for ln in lines:
                raw = ln.strip()
                if not raw:
                    if buffer:
                        cleaned_blocks.append(' '.join(buffer).strip())
                        buffer = []
                    continue

                # Bỏ hoàn toàn dòng là heading markdown
                if raw.startswith('#'):
                    continue

                # Bỏ hoàn toàn các dòng chỉ là tiêu đề in đậm (ví dụ: **Tiêu đề**, **Tóm lại**)
                if _re.match(r'^\*\*.*?\*\*[\s.:-]*$', raw):
                    continue

                # Loại bỏ nhãn in đậm ở đầu dòng nếu có (ví dụ: "**Sự nỗ lực:** Nguyễn Trần..." -> "Nguyễn Trần...")
                raw = _re.sub(r'^\*\*.*?\*\*[\s.:-]*', '', raw).strip()
                if not raw:
                    continue

                norm = _re.sub(r"\s+", " ", _re.sub(r"[^\w\s]", "", raw.lower())).strip()
                if any(norm.startswith(b) for b in banned_starts):
                    # Bỏ hẳn các dòng bắt đầu bằng những cụm này
                    continue

                buffer.append(raw)

            if buffer:
                cleaned_blocks.append(' '.join(buffer).strip())

            if cleaned_blocks:
                rewritten = '\n\n'.join(cleaned_blocks)

            print(f"✅ Groq API thành công!")
            print(f"   - Original: {len(original_content)} chars")
            print(f"   - Rewritten: {len(rewritten)} chars")
            print(f"   - Tokens used: {response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}")
            print(f"   - First 100 chars: {rewritten[:100]}...")
            
            return rewritten
            
        except Exception as e:
            print(f"❌ Lỗi Groq API: {str(e)}")
            print(f"   - API Key present: {bool(self.api_key)}")
            print(f"   - Use AI rewrite: {self.use_ai_rewrite}")
            print("📝 Fallback: Sử dụng nội dung gốc")
            return original_content
    
    
    def _generate_content(self, topic, description, articles, forbidden_keywords=None):
        """
        Tạo nội dung bài viết mới
        Phương pháp: Trích xuất và tổng hợp thông tin quan trọng
        """
        content_parts = []
        
        # Lưu ảnh với thông tin nguồn để chèn SAU KHI AI viết xong
        article_images = []  # List of {'url': ..., 'source': ..., 'caption': ...}
        
        # Phần mở đầu
        intro_templates = [
            f"Trong bối cảnh {topic.lower()} đang trở thành chủ đề được quan tâm rộng rãi, chúng tôi đã tổng hợp thông tin từ nhiều nguồn tin uy tín để mang đến cái nhìn toàn diện nhất.",
            f"{topic} hiện đang là một trong những chủ đề nóng nhất được nhiều người quan tâm. Dưới đây là những thông tin quan trọng nhất.",
            f"Cập nhật mới nhất về {topic.lower()}: Chúng tôi đã phân tích và tổng hợp thông tin từ các nguồn hàng đầu.",
        ]
        
        content_parts.append(random.choice(intro_templates))
        content_parts.append("")  # Empty line
        
        # Tạo các phần nội dung từ TẤT CẢ articles (không giới hạn 3)
        for idx, article in enumerate(articles[:5], 1):  # Lấy tối đa 5 bài
            # Lưu tất cả ảnh từ article với thông tin nguồn
            if article.get('images'):
                # Lấy 2 ảnh đầu tiên từ mỗi article
                for img in article['images'][:2]:
                    article_images.append({
                        'url': img['url'],
                        'source': img['source'],
                        'caption': img.get('caption', article.get('title', ''))
                    })
            elif article.get('image_url'):
                # Fallback nếu chỉ có image_url
                article_images.append({
                    'url': article['image_url'],
                    'source': article.get('source', 'Unknown'),
                    'caption': article.get('title', '')
                })
            
            # Lấy toàn bộ content
            article_content = article.get('content', '')
            
            # Chia content thành paragraphs và làm sạch
            paragraphs = []
            for p in article_content.split('\n'):
                p = p.strip()
                # Bỏ qua đoạn quá ngắn hoặc là link
                if len(p) > 80 and not p.startswith('http') and '://' not in p:
                    paragraphs.append(p)
            
            if paragraphs:
                # Thêm heading với số thứ tự và nguồn
                article_title = article.get('title', 'Thông tin quan trọng')
                source = article.get('source', 'Unknown')
                content_parts.append(f"## {idx}. {article_title}")
                content_parts.append(f"*Nguồn: {source}*")
                content_parts.append("")
                
                # Thêm 4-6 đoạn có nội dung (nhiều hơn)
                count = 0
                for para in paragraphs:
                    if count >= 6:  # Tăng từ 3 lên 6 đoạn
                        break
                    if len(para) > 100:  # Chỉ lấy đoạn có nội dung đầy đủ
                        content_parts.append(para)
                        content_parts.append("")
                        count += 1
        
        # Phần kết
        conclusion_templates = [
            f"Trên đây là những thông tin cập nhật nhất về {topic.lower()}. Chúng tôi sẽ tiếp tục theo dõi và cập nhật thêm thông tin mới.",
            f"Hy vọng bài viết đã cung cấp góc nhìn hữu ích về {topic.lower()}. Hãy theo dõi để cập nhật thêm nhiều thông tin khác.",
            f"Đây là tổng hợp thông tin toàn diện về {topic.lower()} từ nhiều nguồn uy tín. Mời bạn đọc tham khảo các nguồn bên dưới để có thêm thông tin chi tiết.",
        ]
        
        content_parts.append(conclusion_templates[0])
        
        # Ghép nội dung gốc
        original_content = '\n\n'.join(content_parts)
        
        # Sử dụng AI để viết lại nếu có
        if self.use_ai_rewrite:
            print("\n🤖 Đang sử dụng Gemini AI để viết lại nội dung...")
            print(f"📊 Original content length: {len(original_content)} characters")
            print(f"🔑 API Key present: {bool(self.api_key)}")
            print(f"🤖 Client initialized: {hasattr(self, 'client')}")
            
            final_content = self._rewrite_with_ai(original_content, topic, forbidden_keywords)
            
            print(f"📊 Rewritten content length: {len(final_content)} characters")
            
            # Nếu content viết lại quá ngắn, có thể là lỗi
            if len(final_content) < len(original_content) * 0.3:
                print("⚠️ WARNING: Rewritten content too short - using original")
                final_content = original_content
            else:
                print("✅ AI rewrite successful!")
        else:
            print("\n⚠️ Groq API not configured - Using original content")
            final_content = original_content
        
        # Không chèn ảnh trực tiếp vào content nữa vì template đã tự động hiển thị ảnh đại diện (featured image) ở đầu bài viết.
        # Điều này tránh việc hiển thị hai ảnh trùng lặp trong bài viết.
        print(f"\n🖼️ Không chèn ảnh trực tiếp vào bài viết (chỉ sử dụng ảnh đại diện ngoài trang hiển thị).")
        
        raw_paragraphs = [p.strip() for p in final_content.split('\n') if p.strip()]
        paragraphs = []
        for p in raw_paragraphs:
            if p.startswith('#'):
                continue
            if p.startswith('**') and p.endswith('**'):
                continue
            p = re.sub(r'^\*\*.*?\*\*[\s.:-]*', '', p).strip()
            if not p:
                continue
            paragraphs.append(p)
            
        final_content = '\n\n'.join(paragraphs)
        return final_content
    
    
    def generate_article(self, user_id, topic, description, keywords, max_sources=5, forbidden_keywords=None):
        """
        Quy trình hoàn chỉnh: Crawl → Generate → Return
        
        Args:
            user_id: ID người dùng
            topic: Chủ đề
            description: Mô tả
            keywords: Từ khóa
            max_sources: Số bài tối đa để crawl
            forbidden_keywords: Từ khóa cấm
        
        Returns:
            dict: Bài báo mới hoặc None
        """
        start_time = time.time()
        
        print("\n" + "=" * 70)
        print("  🎯 AI ARTICLE GENERATION")
        print("=" * 70)
        print(f"👤 User ID: {user_id}")
        print(f"📌 Topic: {topic}")
        print(f"📝 Description: {description}")
        print(f"🔑 Keywords: {keywords}")
        self._clear_last_error()
        
        # Step 1: Crawl articles — query = "Danh mục + Từ khóa" (ví dụ: "Công nghệ AI")
        _kw = ' '.join(str(keywords or '').split()).strip()
        _cat = ' '.join(str(topic or '').split()).strip()
        _search_query = f"{_cat} {_kw}".strip() if _kw else _cat
        crawled_articles = self.crawl_articles(_search_query, '', max_sources)
        
        if not crawled_articles:
            error_message = (
                f"Không tìm thấy nội dung theo từ khóa trong {self.max_source_age_hours} giờ gần đây. "
                "Vui lòng nhập lại từ khóa hoặc đổi danh mục."
            )
            self._set_last_error(error_message)
            return {
                'success': False,
                'error': error_message
            }
        
        # Step 2: Generate new article
        generated = self.generate_article_from_sources(
            topic, description, keywords, crawled_articles, forbidden_keywords
        )
        
        if not generated:
            return {
                'success': False,
                'error': 'Không thể tạo bài viết từ nguồn đã crawl.'
            }

        # Run validation & rewrite loop
        validated = self._validate_and_sanitize_forbidden_keywords(generated, forbidden_keywords)
        if not validated:
            return {
                'success': False,
                'error': self.last_error or 'Không thể tạo bài viết an toàn (phát hiện từ khóa cấm sau nhiều lần viết lại).'
            }
        generated = validated

        if not self._validate_generated_article_alignment(topic, keywords, generated):
            return {
                'success': False,
                'error': self.last_error or 'Nội dung chưa đạt yêu cầu danh mục/từ khóa.'
            }
        
        generation_time = time.time() - start_time
        
        return {
            'success': True,
            'article': generated,
            'generation_time': round(generation_time, 2),
            'sources_crawled': len(crawled_articles)
        }

    # ----------------------------------
    # MAGAZINE: Generate articles with Google crawl + AI rewrite
    # ----------------------------------
    def generate_articles_for_magazine(self, topic, keywords, magazine_title, description='', count=3, used_source_urls=None):
        """
        Tạo bài viết cho tạp chí: Crawl Google → AI viết lại hoàn toàn.
        Mỗi bài có nội dung khác nhau từ nguồn khác nhau.
        """
        articles = []
        self._clear_last_error()

        # Tập URL nguồn đã dùng (từ DB + các bài sinh trong cùng phiên gọi này)
        if used_source_urls is None:
            used_source_urls = set()
        else:
            used_source_urls = {u.strip() for u in used_source_urls if isinstance(u, str) and u.strip()}

        # Query tìm kiếm = "Danh mục + Từ khóa" (ví dụ: "Công nghệ AI")
        kw_clean = ' '.join(str(keywords or '').split()[:6]).strip()
        base_query_core = f"{str(topic or '').strip()} {kw_clean}".strip()
        if not base_query_core:
            base_query_core = str(topic or '').strip()
        
        # Danh sách angles đa dạng hơn với từ khóa unique
        all_angles = [
            {"angle": f"xu hướng công nghệ mới trong {topic}", "suffix": "công nghệ mới nhất", "focus": "technology"},
            {"angle": f"phân tích chiến thuật {keywords}", "suffix": "phân tích chiến thuật", "focus": "tactics"}, 
            {"angle": f"tương lai phát triển {topic}", "suffix": "dự báo phát triển", "focus": "future"},
            {"angle": f"bí quyết thành công {keywords}", "suffix": "bí quyết chuyên gia", "focus": "success"},
            {"angle": f"so sánh và đối chiếu {topic}", "suffix": "so sánh chi tiết", "focus": "comparison"},
            {"angle": f"thực trạng và thách thức {keywords}", "suffix": "thực trạng hiện tại", "focus": "challenges"},  
            {"angle": f"kinh nghiệm từ chuyên gia {topic}", "suffix": "kinh nghiệm chuyên gia", "focus": "expertise"},
            {"angle": f"cập nhật tin tức nóng {keywords}", "suffix": "tin tức nóng hổi", "focus": "news"},
            {"angle": f"đánh giá performance {topic}", "suffix": "đánh giá chi tiết", "focus": "analysis"},
            {"angle": f"hướng dẫn chi tiết {keywords}", "suffix": "hướng dẫn từ A-Z", "focus": "guide"},
            {"angle": f"thống kê và số liệu {topic}", "suffix": "thống kê quan trọng", "focus": "statistics"},
            {"angle": f"tranh cãi và ý kiến {keywords}", "suffix": "góc nhìn tranh cãi", "focus": "controversy"},
            {"angle": f"lịch sử và truyền thống {topic}", "suffix": "lịch sử phát triển", "focus": "history"},
            {"angle": f"marketing và thương mại {keywords}", "suffix": "khía cạnh thương mại", "focus": "business"},
            {"angle": f"impact xã hội {topic}", "suffix": "tác động xã hội", "focus": "social"},
        ]
        
        # Random shuffle với seed dựa trên timestamp để tránh trùng lặp
        import random
        import time
        random.seed(int(time.time()) + hash(topic + keywords))  # Dynamic seed cho đa dạng nội dung
        random.shuffle(all_angles)
        
        # Chọn số lượng angles cần thiết
        # Loại bỏ angles đã dùng gần đây (simple cache)
        if not hasattr(self, '_used_angles'):
            self._used_angles = []
        
        available_angles = [a for a in all_angles if a['focus'] not in self._used_angles[-5:]]
        if len(available_angles) < count:
            available_angles = all_angles  # Reset nếu không đủ
            
        angles = available_angles[:count]
        
        # Ghi nhớ angles đã dùng
        for angle in angles:
            self._used_angles.append(angle['focus'])
            if len(self._used_angles) > 10:  # Giới hạn cache
                self._used_angles = self._used_angles[-10:]

        # Thử nhận diện xem topic có phải là một danh mục VnExpress cụ thể không
        vn_cat_url = self._detect_vnexpress_category_url(topic or description)

        for i in range(min(count, len(angles))):
            angle_data = angles[i]

            # Thêm timestamp nhẹ để tránh cache nhưng vẫn bám sát CHỦ ĐỀ + MÔ TẢ
            import time
            timestamp_suffix = str(int(time.time() % 1000))[-2:]

            # Query chính: danh mục (topic) + mô tả tạp chí, có thể thêm hậu tố góc nhìn
            if angle_data.get('suffix') and description:
                search_query = f"{base_query_core} {angle_data['suffix']} {timestamp_suffix}"
            else:
                search_query = f"{base_query_core} {timestamp_suffix}".strip()

            crawled = []

            # 1) Nếu topic map được sang danh mục VnExpress thì ưu tiên crawl danh mục đó
            if vn_cat_url:
                print(f"\n[CRAWL] [{i+1}/{count}] Using VnExpress category: {vn_cat_url}")
                cat_articles = self._crawl_vnexpress_category(vn_cat_url, max_articles=6)
                for art in cat_articles:
                    url = (art.get('url') or '').strip()
                    if url and (url in used_source_urls or url in self._crawled_urls_cache):
                        print(f"  [SKIP] Category URL already used: {url[:80]}")
                        continue
                    crawled.append(art)

            # 2) Nếu không crawl được từ danh mục (hoặc không có mapping), fallback về search như cũ
            if not crawled:
                print(f"\n[CRAWL] [{i+1}/{count}] Searching: {search_query}")

                # Crawl từ Google theo nhiều query nhưng LUÔN neo theo topic + description
                urls = self.search_google_news(search_query, description, max_results=10)
                if len(urls) < 3:
                    urls += self.search_google_news(base_query_core, description, max_results=10)
                if len(urls) < 3:
                    urls += self.search_google_news(f"{topic} Việt Nam", description, max_results=10)

                # Khử trùng lặp URL
                dedup_urls = []
                seen = set()
                for u in urls:
                    if isinstance(u, str) and u not in seen:
                        dedup_urls.append(u)
                        seen.add(u)

                for url in dedup_urls[:5]:  # Crawl tối đa 5 URL đầu để tăng độ phong phú nguồn
                    url_str = (url or '').strip()
                    if url_str and (url_str in used_source_urls or url_str in self._crawled_urls_cache):
                        print(f"  [SKIP] URL already used: {url_str[:80]}")
                        continue
                    try:
                        art = self._crawl_article_content(url)
                        if art:
                            src_url = (art.get('url') or '').strip()
                            if src_url and (src_url in used_source_urls or src_url in self._crawled_urls_cache):
                                print(f"  [SKIP] Crawled URL already used: {src_url[:80]}")
                                continue
                            if src_url:
                                self._crawled_urls_cache.add(src_url)
                            crawled.append(art)
                            print(f"  [+] {art['source']}: {art['title'][:50]}")
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"  [-] Error: {str(e)[:60]}")

                # Bổ sung dữ liệu đa nguồn từ RSS nếu số nguồn còn ít
                distinct_sources = len(set([c.get('source', '').strip().lower() for c in crawled if c.get('source')]))
                if len(crawled) < 4 or distinct_sources < 2:
                    try:
                        need = max(4, 6 - len(crawled))
                        print(f"  [INFO] Bổ sung dữ liệu RSS đa nguồn (need={need})...")

                        # Dùng topic + keywords để lọc RSS sát nội dung hơn
                        rss_query = kw_clean or description or topic
                        rss_articles = self._crawl_rss_multisource(topic, rss_query, max_articles=need)
                        seen_urls_rss = {c.get('url') for c in crawled if c.get('url')}
                        for article_rss in rss_articles:
                            url_rss = (article_rss.get('url') or '').strip()
                            if not url_rss or url_rss in seen_urls_rss or url_rss in used_source_urls:
                                continue
                            crawled.append(article_rss)
                            seen_urls_rss.add(url_rss)

                        # Nếu vẫn chưa đa nguồn, nới lỏng lọc từ khóa để lấy thêm domain
                        distinct_sources = len(set([c.get('source', '').strip().lower() for c in crawled if c.get('source')]))
                        if distinct_sources < 2:
                            print("  [INFO] Chưa đủ đa nguồn, thử RSS không lọc từ khóa...")
                            rss_relaxed = self._crawl_rss_multisource(topic, rss_query, max_articles=need, keyword_filter=False)
                            for article_rss in rss_relaxed:
                                url_rss = (article_rss.get('url') or '').strip()
                                if not url_rss or url_rss in seen_urls_rss or url_rss in used_source_urls:
                                    continue
                                crawled.append(article_rss)
                                seen_urls_rss.add(url_rss)
                    except Exception as e:
                        print(f"  [WARN] RSS enrichment failed: {str(e)[:80]}")

                # Fallback crawl nguồn trực tiếp nếu Google không trả URL dùng được
                if not crawled:
                    try:
                        print("  [INFO] Google crawl trống, thử crawl trực tiếp từ VnExpress search...")
                        direct_crawled = self._crawl_vnexpress(base_query_core or topic, 4)
                        if direct_crawled:
                            for art in direct_crawled:
                                url_dc = (art.get('url') or '').strip()
                                if url_dc and url_dc in used_source_urls:
                                    print(f"  [SKIP] Direct VnExpress URL already used: {url_dc[:80]}")
                                    continue
                                crawled.append(art)
                            print(f"  [OK] Direct crawl got {len(crawled)} articles (after dedup)")
                    except Exception as e:
                        print(f"  [WARN] Direct crawl failed: {str(e)[:80]}")
            
            if not crawled:
                print("  [WARN] No source content found for this keyword/category; skip article.")
                self._set_last_error(
                    "Không tìm thấy nội dung theo từ khóa/danh mục đã chọn. "
                    "Vui lòng nhập lại từ khóa hoặc đổi danh mục."
                )
                article = None
            else:
                unique_sources = sorted({c.get('source', 'Unknown') for c in crawled if c.get('source')})
                print(f"  [SRC] Using {len(unique_sources)} source domains: {', '.join(unique_sources[:5])}")

                # Gộp content từ các bài crawl
                combined_content = "\n\n---SOURCE---\n\n".join([
                    f"[{c['source']}] {c['title']}\n{c['content'][:1500]}" 
                    for c in crawled
                ])
                source_brief = self._build_sources_brief(crawled, max_items=6)
                
                # Lấy TẤT CẢ ảnh từ các bài crawl (tối đa 5 ảnh)
                crawled_images = []
                seen_urls = set()
                for c in crawled:
                    # Ưu tiên image_url chính
                    img = c.get('image_url')
                    if img and img.startswith('http') and img not in seen_urls:
                        crawled_images.append({'url': img, 'caption': c.get('title', '')})
                        seen_urls.add(img)
                    # Lấy thêm từ images array
                    for img_data in c.get('images', []):
                        img_url = img_data.get('url') if isinstance(img_data, dict) else img_data
                        if img_url and img_url.startswith('http') and img_url not in seen_urls:
                            caption = img_data.get('caption', '') if isinstance(img_data, dict) else ''
                            crawled_images.append({'url': img_url, 'caption': caption})
                            seen_urls.add(img_url)
                    if len(crawled_images) >= 5:
                        break
                
                print(f"  [IMG] Found {len(crawled_images)} images from crawl")
                for idx, img in enumerate(crawled_images[:3]):
                    print(f"    [{idx+1}] {img['url'][:60]}...")
                
                # AI viết lại hoàn toàn dựa trên nội dung crawl
                article = self._generate_single_article_with_crawl(
                    topic=topic,
                    keywords=keywords,
                    magazine_title=magazine_title,
                    description=description,
                    angle=angle_data['angle'],
                    focus=angle_data.get('focus', 'general'),
                    crawled_content=combined_content,
                    source_brief=source_brief,
                    crawled_images=crawled_images  # Truyền list thay vì single image
                )
                if article:
                    src_urls = [c.get('url') for c in crawled if c.get('url')]
                    article['source_urls'] = src_urls
                    for u in src_urls:
                        if isinstance(u, str) and u.strip().startswith('http'):
                            used_source_urls.add(u.strip())
                            self._crawled_urls_cache.add(u.strip())

                    if not self._validate_generated_article_alignment(topic, keywords, article):
                        print("  [REVIEW] Article skipped due to category/keyword mismatch")
                        article = None
            
            if article:
                articles.append(article)
                print(f"  [OK] Article generated: {article['title'][:60]}")

        print(f"\n[OK] Generated {len(articles)}/{count} articles for magazine '{magazine_title}'")
        return articles

    def generate_single_article_for_category(self, topic, magazine_title, description='', keywords='', forbidden_keywords=None):
        """Tạo đúng 1 bài cho một danh mục.

        Logic mới:
        - Query tìm nguồn chính: "{Danh mục} {Từ khóa danh mục}" (ví dụ: "du lịch Đà Lạt").
        - Mô tả tạp chí/danh mục chỉ dùng để filter thêm, không làm loãng query.
        - Mỗi lần gọi cố gắng chọn 1 URL nguồn CHƯA dùng để tránh trùng bài.
        """

        print("\n" + "=" * 70)
        print("  🎯 GENERATE SINGLE ARTICLE FOR CATEGORY")
        print("=" * 70)
        print(f"📌 Category (topic): {topic}")
        print(f"📝 Description: {description}")
        print(f"🔑 Category keywords: {keywords}")
        self._clear_last_error()

        # Giới hạn tối đa ~25 giây cho việc crawl 1 bài, tránh treo request
        start_ts = time.time()

        # Bộ nhớ URL đã dùng để không lặp lại nguồn
        used_urls = getattr(self, "_used_single_category_urls", set())
        best_article = None

        # Query = "Danh mục + Từ khóa" (ví dụ: "Công nghệ AI")
        base_topic = str(topic or "").strip()
        kw_core = " ".join(str(keywords or "").split()[:6]).strip()
        search_query = " ".join(filter(None, [base_topic, kw_core])).strip()

        if not search_query:
            search_query = base_topic or kw_core or str(description or "").strip()

        print(f"🔍 Searching (category+keywords): {search_query}")

        # 1a) Ưu tiên Google News (6 báo lớn, tin mới nhất, tránh trùng)
        try:
            google_urls = self.search_google_news(search_query, '', max_results=10)
            for g_url in google_urls:
                if time.time() - start_ts > 20:
                    break
                g_url = (g_url or '').strip()
                if not g_url or g_url in used_urls or g_url in self._crawled_urls_cache:
                    continue
                art = self._crawl_article_content(g_url)
                if art:
                    best_article = art
                    self._crawled_urls_cache.add(g_url)
                    print(f"  ✅ Chọn bài từ Google: {art.get('title','')[:80]}")
                    break
        except Exception as e:
            print(f"  ❌ Lỗi Google search: {str(e)[:80]}")

        # 1b) Fallback: VnExpress search trực tiếp
        if not best_article:
            try:
                vn_articles = self._crawl_vnexpress(search_query, max_articles=5, skip_urls=used_urls)
                for art in vn_articles:
                    if time.time() - start_ts > 25:
                        break
                    url = art.get("url")
                    if url and (url in used_urls or url in self._crawled_urls_cache):
                        print("  ↳ Bỏ qua vì URL này đã dùng.")
                        continue
                    best_article = art
                    print(f"  ✅ Chọn bài từ VnExpress: {art.get('title','')[:80]}")
                    break
            except Exception as e:
                print(f"  ❌ Lỗi VnExpress search: {str(e)[:80]}")

        # Không có nguồn thật thì dừng, không cho AI tự viết.
        if not best_article:
            error_message = (
                "Không tìm thấy bài viết phù hợp với từ khóa/danh mục đã nhập. "
                "Vui lòng thử lại với từ khóa khác hoặc đổi danh mục."
            )
            print(f"  ⚠️ {error_message}")
            self._set_last_error(error_message)
            return None

        # 5) Dùng đúng 1 bài nguồn để AI viết lại
        best_url = (best_article.get("url") or '').strip()
        if best_url:
            used_urls.add(best_url)
            self._crawled_urls_cache.add(best_url)
        setattr(self, "_used_single_category_urls", used_urls)

        generated = self.generate_article_from_sources(
            topic=topic,
            description=description,
            keywords=keywords or "",
            crawled_articles=[best_article],
            forbidden_keywords=forbidden_keywords,
        )
        if not generated:
            return None

        # Run safety validation and sanitization loop
        validated = self._validate_and_sanitize_forbidden_keywords(generated, forbidden_keywords)
        if not validated:
            return None
        generated = validated

        # Chỉ dùng heuristic check (không gọi LLM reviewer)
        # để tránh tốn Groq API quota khi tạo nhiều bài cùng lúc.
        heuristic = self._heuristic_alignment_agent(
            topic=topic,
            keywords=keywords,
            article=generated,
            agent_name='heuristic-bulk',
            min_keyword_ratio=0.10,   # Ngưỡng thấp hơn, vì bài đã crawl đúng chủ đề
        )
        if not heuristic.get('pass'):
            # Soft warning: vẫn trả về bài (nguồn đã crawl đúng query),
            # chỉ log để debug
            print(f"  [REVIEW-SOFT] Heuristic soft-fail: {heuristic.get('rationale','')} — vẫn giữ bài")

        return generated

    def _generate_single_article_with_crawl(self, topic, keywords, magazine_title, description, angle, focus, crawled_content, source_brief='', crawled_images=None):
        """Viết lại hoàn toàn bài viết dựa trên nội dung đã crawl, bám sát mô tả & danh mục.

        Ghi chú: tham số `keywords` chỉ còn mang tính nội bộ (giữ tương thích),
        AI được yêu cầu bám sát CHỦ ĐỀ (topic) và MÔ TẢ (description), không dựa vào
        một danh sách từ khóa do người dùng nhập.
        """
        import random
        import time
        
        # Đảm bảo crawled_images là list
        if crawled_images is None:
            crawled_images = []
        
        # Nếu không có AI (hoặc tắt rewrite), ta vẫn dùng NỘI DUNG ĐÃ CRAWL
        # để tạo bài viết 3 đoạn bằng parser nội bộ, tránh dùng template chung chung.
        if not self.use_ai_rewrite or not self.client:
            print("[INFO] AI rewrite disabled or client missing – using crawled content directly")
            parsed = self._parse_magazine_article(crawled_content, topic, keywords, description)

            # Xử lý hình ảnh giống nhánh AI ở phía dưới
            if crawled_images:
                parsed['image_url'] = crawled_images[0]['url']
                print(f"  [IMG] Main image: {crawled_images[0]['url'][:70]}")

                if len(crawled_images) > 1:
                    parsed['content'] = self._insert_images_into_content(
                        parsed.get('content', ''),
                        crawled_images[1:]
                    )
                    print(f"  [IMG] Inserted {len(crawled_images)-1} images into content")

                parsed['all_images'] = [img['url'] for img in crawled_images]
            else:
                if not parsed.get('image_url'):
                    parsed['image_url'] = self._fallback_image_url(angle)
                    print(f"  [IMG] Fallback: {parsed['image_url'][:70]}")
                parsed['all_images'] = parsed.get('all_images') or ([parsed['image_url']] if parsed.get('image_url') else [])

            if not parsed.get('image_url'):
                parsed['image_url'] = self._fallback_image_url(parsed.get('title', angle))
                print(f"  [IMG] Emergency fallback: {parsed['image_url'][:70]}")

            return parsed

        json_example = "{\n  \"title\": \"Tiêu đề bài viết\",\n  \"sapo\": \"Đoạn sapo\",\n  \"content\": \"Nội dung bài viết\"\n}"
        prompt = f"""Bạn là AI E-Magazine Writer, một biên tập viên báo điện tử chuyên nghiệp của tạp chí "{magazine_title}" với chuyên môn về {focus}.

NHIỆM VỤ: Dựa trên thông tin từ nhiều nguồn tin tức dưới đây, hãy viết MỘT BÀI BÁO HOÀN TOÀN MỚI theo góc nhìn "{angle}" và danh mục "{topic}" (Mô tả danh mục: {description}).

===== NGUỒN THAM KHẢO =====
{crawled_content[:7000]}
===== HẾT NGUỒN =====

===== TÓM TẮT NGUỒN ƯU TIÊN =====
{source_brief[:3000]}
===== HẾT TÓM TẮT =====

YÊU CẦU BẮT BUỘC VỀ NỘI DUNG (MỤC TIÊU):
- Bài viết phải khách quan, chính xác, dễ đọc, giàu thông tin, không lặp ý, không suy diễn, không bịa đặt, không thiên vị, và tự nhiên như được viết bởi biên tập viên chuyên nghiệp.
- Tuyệt đối KHÔNG viết giống văn nghị luận học đường. Không dùng các mẫu câu máy móc, không viết kiểu giáo điều/dạy đời/cổ vũ/kết luận thay độc giả.
- CHỈ sử dụng thông tin có thực xuất hiện trong dữ liệu nguồn. Không bổ sung thông tin từ trí nhớ, không tạo số liệu mới, không tạo trích dẫn/phát biểu/địa điểm/thời gian giả mạo.
- Giọng văn: trung lập, khách quan, hiện đại, rõ ràng, súc tích. Không dùng văn phong cảm tính.
- Độ dài: Từ 900-1500 từ (nếu dữ liệu phong phú) hoặc 500-700 từ (nếu dữ liệu ít). Không viết để đủ chữ.
- Cấu trúc nội dung: Bài viết gồm các đoạn văn xuôi mạch lạc liên kết chặt chẽ với nhau (không dùng gạch đầu dòng, không dùng danh sách liệt kê). Nội dung đi thẳng vào vấn đề chính, tiếp nối bằng phân tích diễn biến thực tế, bối cảnh liên quan và mở rộng góc nhìn, kết thúc khách quan mà không triết lý sáo rỗng. Tuyệt đối KHÔNG sử dụng các tiêu đề rập khuôn như "Mở đầu", "Diễn biến", "Bối cảnh", "Kết luận".
- Chống lặp ý: Mỗi đoạn chỉ trình bày MỘT ý mới, không nhắc lại ý cũ. Không lặp cấu trúc, câu, từ khóa.
- KHÔNG sử dụng các từ/cụm từ sau: "Có thể thấy", "Điều này cho thấy", "Một trong những", "Không chỉ", "Bên cạnh đó", "Hơn nữa", "Qua đó", "Theo nghiên cứu", "Theo báo cáo", "Tóm lại", "Nhìn chung", "Cuối cùng".
- Ngôn ngữ: Ưu tiên câu ngắn (20-30 từ). Sử dụng động từ mạnh, hạn chế tính từ và trạng từ sáo rỗng.
- SEO & H2: Tạo các heading H2 (dạng ## [Tên heading]) hợp lý trong nội dung nếu bài dài trên 800 từ (tối đa 6 heading). Tuyệt đối không đặt tên heading dạng "Mở đầu", "Giới thiệu", "Nội dung", "Kết luận" hay từ rập khuôn tương tự.
- Đa dạng câu: Không viết các câu liên tiếp bắt đầu bằng cùng một từ hoặc cấu trúc chủ ngữ giống hệt nhau.

ĐẦU RA:
Bạn bắt buộc phải trả về kết quả dưới dạng đối tượng JSON thuần túy (không chứa ký hiệu markdown ```json hay text giải thích). Cấu trúc JSON như sau:
{json_example}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là AI E-Magazine Writer, một biên tập viên báo điện tử chuyên nghiệp và luôn trả về kết quả định dạng JSON chính xác."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=4096,
                top_p=0.95
            )
            raw = response.choices[0].message.content
            
            # Thử parse JSON trước
            parsed = None
            cleaned_raw = raw.strip()
            if cleaned_raw.startswith("```"):
                cleaned_raw = re.sub(r"^```[a-zA-Z]*\n", "", cleaned_raw)
                cleaned_raw = re.sub(r"\n```$", "", cleaned_raw)
            cleaned_raw = cleaned_raw.strip()
            try:
                import json
                parsed_json = json.loads(cleaned_raw, strict=False)
                if parsed_json and isinstance(parsed_json, dict) and "title" in parsed_json:
                    parsed = {
                        'title': parsed_json.get('title', '').strip(),
                        'summary': parsed_json.get('sapo', parsed_json.get('summary', '')).strip(),
                        'content': parsed_json.get('content', '').strip(),
                        'keywords': keywords,
                        'topic': topic,
                        'image_url': '',
                        'all_images': []
                    }
                    print("✅ AI JSON parsed successfully in _generate_single_article_with_crawl!")
            except Exception as json_err:
                print(f"[WARN] Failed to parse AI JSON, falling back to heuristics parser: {json_err}")
                parsed = None

            if not parsed:
                parsed = self._parse_magazine_article(raw, topic, keywords, description)

            parsed['content'] = self._ensure_minimum_content(
                parsed.get('content', ''), topic, keywords, min_words=1800
            )
            parsed['content'] = self._deduplicate_content_blocks(parsed.get('content', ''))
            # Bỏ normalize và limit section vì user không muốn heading
            # parsed['content'] = self._normalize_article_structure(parsed.get('content', ''))
            # parsed['content'] = self._limit_content_sections(parsed.get('content', ''), max_sections=5)
            
            # Xử lý hình ảnh: lấy ảnh chính và chèn các ảnh khác vào content
            if crawled_images:
                # Ảnh chính là ảnh đầu tiên
                parsed['image_url'] = crawled_images[0]['url']
                print(f"  [IMG] Main image: {crawled_images[0]['url'][:70]}")
                
                # Chèn các ảnh còn lại vào giữa nội dung
                if len(crawled_images) > 1:
                    parsed['content'] = self._insert_images_into_content(
                        parsed.get('content', ''),
                        crawled_images[1:]  # Các ảnh từ thứ 2 trở đi
                    )
                    print(f"  [IMG] Inserted {len(crawled_images)-1} images into content")
                
                # Lưu tất cả URLs vào image_urls để hiển thị
                parsed['all_images'] = [img['url'] for img in crawled_images]
            elif not parsed.get('image_url') or parsed['image_url'] == '':
                # Nếu không có ảnh crawl và AI không trả về ảnh
                parsed['image_url'] = self._fallback_image_url(angle)
                print(f"  [IMG] Fallback: {parsed['image_url'][:70]}")
            else:
                print(f"  [IMG] From AI: {parsed['image_url'][:70]}")
            
            # FINAL CHECK: Ensure image_url is never empty
            if not parsed.get('image_url'):
                parsed['image_url'] = self._fallback_image_url(parsed.get('title', angle))
                print(f"  [IMG] Emergency fallback: {parsed['image_url'][:70]}")

            if not parsed.get('all_images'):
                parsed['all_images'] = [parsed['image_url']] if parsed.get('image_url') else []

            return parsed
        except Exception as e:
            # Nếu AI bị lỗi, vẫn ưu tiên dùng nội dung đã crawl thay vì template chung
            print(f"[WARN] Groq error: {e} – falling back to crawled content parser")
            parsed = self._parse_magazine_article(crawled_content, topic, keywords, description)

            if crawled_images:
                parsed['image_url'] = crawled_images[0]['url']
                print(f"  [IMG] Main image (fallback): {crawled_images[0]['url'][:70]}")
                if len(crawled_images) > 1:
                    parsed['content'] = self._insert_images_into_content(
                        parsed.get('content', ''),
                        crawled_images[1:]
                    )
                    print(f"  [IMG] Inserted {len(crawled_images)-1} images into content (fallback)")
                parsed['all_images'] = [img['url'] for img in crawled_images]
            else:
                if not parsed.get('image_url'):
                    parsed['image_url'] = self._fallback_image_url(angle)
                parsed['all_images'] = parsed.get('all_images') or ([parsed['image_url']] if parsed.get('image_url') else [])

            if not parsed.get('image_url'):
                parsed['image_url'] = self._fallback_image_url(parsed.get('title', angle))

            return parsed

    def _generate_single_article_direct(self, topic, keywords, magazine_title, description, angle, image_url=''):
        """Gọi Groq API tạo một bài viết hoàn chỉnh (fallback khi không crawl được)."""
        if not self.use_ai_rewrite or not self.client:
            return self._fallback_magazine_article(topic, keywords, angle)

        json_example = "{\n  \"title\": \"Tiêu đề bài viết\",\n  \"sapo\": \"Đoạn sapo\",\n  \"content\": \"Nội dung bài viết\"\n}"
        prompt = f"""Bạn là AI E-Magazine Writer, một biên tập viên báo điện tử chuyên nghiệp của tạp chí điện tử "{magazine_title}".

Thông tin tạp chí:
- Chủ đề chính: {topic}
- Mô tả: {description if description else 'Không có'}
- Từ khóa tham khảo: {keywords}

NHIỆM VỤ: Viết một bài báo HOÀN CHỈNH bằng tiếng Việt theo góc nhìn "{angle}" và danh mục "{topic}".

YÊU CẦU BẮT BUỘC VỀ NỘI DUNG (MỤC TIÊU):
- Bài viết phải khách quan, chính xác, dễ đọc, giàu thông tin, không lặp ý, không suy diễn, không bịa đặt, không thiên vị, và tự nhiên như được viết bởi biên tập viên chuyên nghiệp.
- Tuyệt đối KHÔNG viết giống văn nghị luận học đường. Không dùng các mẫu câu máy móc, không viết kiểu giáo điều/dạy đời/cổ vũ/kết luận thay độc giả.
- Giọng văn: trung lập, khách quan, hiện đại, rõ ràng, súc tích. Không dùng văn phong cảm tính.
- Độ dài: Từ 900-1200 từ hoặc 500-700 từ tùy thuộc vào dữ liệu. Không viết để đủ chữ.
- Cấu trúc nội dung: Bài viết gồm các đoạn văn xuôi mạch lạc liên kết chặt chẽ với nhau (không dùng gạch đầu dòng, không dùng danh sách liệt kê). Nội dung đi thẳng vào vấn đề chính, tiếp nối bằng phân tích diễn biến thực tế, bối cảnh liên quan và mở rộng góc nhìn, kết thúc khách quan mà không triết lý sáo rỗng. Tuyệt đối KHÔNG sử dụng các tiêu đề rập khuôn như "Mở đầu", "Diễn biến", "Bối cảnh", "Kết luận".
- Chống lặp ý: Mỗi đoạn chỉ trình bày MỘT ý mới, không nhắc lại ý cũ. Không lặp cấu trúc, câu, từ khóa.
- KHÔNG sử dụng các từ/cụm từ sau: "Có thể thấy", "Điều này cho thấy", "Một trong những", "Không chỉ", "Bên cạnh đó", "Hơn nữa", "Qua đó", "Theo nghiên cứu", "Theo báo cáo", "Tóm lại", "Nhìn chung", "Cuối cùng".
- Ngôn ngữ: Ưu tiên câu ngắn (20-30 từ). Sử dụng động từ mạnh, hạn chế tính từ và trạng từ sáo rỗng.
- SEO & H2: Tạo các heading H2 (dạng ## [Tên heading]) hợp lý trong nội dung nếu bài dài trên 800 từ (tối đa 6 heading). Tuyệt đối không đặt tên heading dạng "Mở đầu", "Giới thiệu", "Nội dung", "Kết luận" hay từ rập khuôn tương tự.
- Đa dạng câu: Không viết các câu liên tiếp bắt đầu bằng cùng một từ hoặc cấu trúc chủ ngữ giống hệt nhau.

ĐẦU RA:
Bạn bắt buộc phải trả về kết quả dưới dạng đối tượng JSON thuần túy (không chứa ký hiệu markdown ```json hay text giải thích). Cấu trúc JSON như sau:
{json_example}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là AI E-Magazine Writer, một biên tập viên báo điện tử chuyên nghiệp và luôn trả về kết quả định dạng JSON chính xác."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.75,
                max_tokens=2000
            )
            raw = response.choices[0].message.content
            
            # Thử parse JSON trước
            parsed = None
            cleaned_raw = raw.strip()
            if cleaned_raw.startswith("```"):
                cleaned_raw = re.sub(r"^```[a-zA-Z]*\n", "", cleaned_raw)
                cleaned_raw = re.sub(r"\n```$", "", cleaned_raw)
            cleaned_raw = cleaned_raw.strip()
            try:
                import json
                parsed_json = json.loads(cleaned_raw, strict=False)
                if parsed_json and isinstance(parsed_json, dict) and "title" in parsed_json:
                    parsed = {
                        'title': parsed_json.get('title', '').strip(),
                        'summary': parsed_json.get('sapo', parsed_json.get('summary', '')).strip(),
                        'content': parsed_json.get('content', '').strip(),
                        'keywords': keywords,
                        'topic': topic,
                        'image_url': image_url,
                        'all_images': [image_url] if image_url else []
                    }
                    print("✅ AI JSON parsed successfully in _generate_single_article_direct!")
            except Exception as json_err:
                print(f"[WARN] Failed to parse AI JSON, falling back to heuristics parser: {json_err}")
                parsed = None

            if not parsed:
                parsed = self._parse_magazine_article(raw, topic, keywords, description, image_url)
                
            return parsed
        except Exception as e:
            print(f"[WARN] Groq error for '{angle[:40]}': {e}")
            return self._fallback_magazine_article(topic, keywords, angle)

    @staticmethod
    def _build_image_url(image_keywords_en):
        """Build loremflickr URL from English keywords returned by AI"""
        if not image_keywords_en:
            return ''
        parts = [k.strip().replace(' ', '-').lower() for k in image_keywords_en.split(',') if k.strip()][:3]
        if not parts:
            return ''
        return f"https://loremflickr.com/800/420/{','.join(parts)}"

    @staticmethod
    def _fallback_image_url(seed_text='article'):
        seed = abs(hash(seed_text)) % 999999
        return f"https://picsum.photos/seed/{seed}/1200/700"

    def _fetch_wikimedia_image(self, topic, keywords=''):
        """Lấy ảnh có nguồn từ Wikimedia Commons theo chủ đề"""
        try:
            import urllib.parse

            query_terms = [str(topic or '').strip()]
            query_terms.extend([
                p.strip() for p in str(keywords or '').split(',')
                if p and p.strip()
            ])

            for term in query_terms[:3]:
                if not term:
                    continue
                search_term = urllib.parse.quote_plus(term)
                api_url = (
                    "https://commons.wikimedia.org/w/api.php"
                    f"?action=query&generator=search&gsrsearch={search_term}"
                    "&gsrnamespace=6&gsrlimit=5&prop=imageinfo&iiprop=url&format=json"
                )
                resp = requests.get(api_url, headers=self.headers, timeout=7)
                data = resp.json()
                pages = (data.get('query') or {}).get('pages') or {}
                for _, page in pages.items():
                    infos = page.get('imageinfo') or []
                    if not infos:
                        continue
                    image_url = infos[0].get('url')
                    title = page.get('title', '')
                    if image_url and title:
                        source_url = f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}"
                        return image_url, source_url
        except Exception:
            return '', ''
        return '', ''

    def _ensure_minimum_content(self, content, topic, keywords, min_words=700):
        """Đảm bảo nội dung đủ dài nhưng KHÔNG chèn thêm khung template cố định.

        Người dùng phản hồi rằng các đoạn như "Bối cảnh và xu hướng...", "Phân tích chuyên sâu theo danh mục",
        "Gợi ý ứng dụng thực tế", "Kết luận", "Kết nối thực tiễn" làm bài viết trông lặp và giả tạo.
        Vì vậy, từ giờ hàm này chỉ đảm bảo có nội dung cơ bản, KHÔNG tự động chèn thêm các heading/template.
        """
        text = (content or '').strip()

        # Nếu hoàn toàn rỗng thì tạo một đoạn mở đầu ngắn gọn, không heading
        if not text:
            return (
                f"{topic} hiện là chủ đề nhận được nhiều sự quan tâm. "
                f"Bài viết này tổng hợp một số thông tin chính liên quan đến {keywords}."
            )

        # Giữ nguyên content gốc, không cố ép dài thêm để tránh sinh ra cấu trúc thừa
        return text

    def _deduplicate_content_blocks(self, content):
        """Loại bỏ block lặp để nội dung mạch lạc hơn"""
        if not content:
            return content

        blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
        unique_blocks = []
        seen = set()
        seen_headings = set()

        for block in blocks:
            is_heading = block.startswith('##')
            normalized = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', block.lower())).strip()
            if not normalized:
                continue

            if is_heading:
                if normalized in seen_headings:
                    continue
                seen_headings.add(normalized)

            if normalized in seen:
                continue

            near_dup = False
            for old in seen:
                if len(normalized) > 120 and (normalized in old or old in normalized):
                    near_dup = True
                    break
            if near_dup:
                continue

            seen.add(normalized)
            unique_blocks.append(block)

        return '\n\n'.join(unique_blocks)

    def _limit_content_sections(self, content, max_sections=5):
        """Giới hạn tối đa số mục heading ## trong nội dung"""
        if not content:
            return content

        blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
        limited_blocks = []
        heading_count = 0
        drop_rest = False

        for block in blocks:
            is_heading = block.startswith('##')
            if is_heading:
                heading_count += 1
                if heading_count > max_sections:
                    drop_rest = True
                    continue
                drop_rest = False

            if drop_rest:
                continue

            limited_blocks.append(block)

        return '\n\n'.join(limited_blocks)

    def _normalize_article_structure(self, content):
        """Chuẩn hóa heading và xuống dòng để giữ cấu trúc bài viết ổn định"""
        if not content:
            return content

        text = str(content)
        # Đồng nhất heading về ##
        text = re.sub(r'(?m)^\s*#{3,}\s*', '## ', text)
        # Nếu heading bị dính sau đoạn văn thì tách ra dòng riêng
        text = re.sub(r'([^\n])\s*(##\s+)', r'\1\n\n\2', text)
        # Chuẩn hóa nhiều dòng trống liên tiếp
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Làm sạch heading có dấu ngoặc kép dư
        text = re.sub(r'(?m)^##\s+["\'](.+?)["\']\s*$', r'## \1', text)

        # Nếu AI không trả heading markdown, tự chia 5 mục để giữ cấu trúc ổn định
        if not re.search(r'(?m)^##\s+.+$', text):
            paragraphs = [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]
            if len(paragraphs) >= 5:
                intro = paragraphs[0]
                body = paragraphs[1:]
                chunk_size = max(1, len(body) // 5)
                section_titles = [
                    "## Bối cảnh hiện tại",
                    "## Phân tích trọng tâm",
                    "## Dữ liệu và ví dụ thực tế",
                    "## Tác động và cơ hội",
                    "## Khuyến nghị cho người đọc"
                ]
                rebuilt = [intro]
                idx = 0
                for i, title in enumerate(section_titles):
                    if idx >= len(body):
                        break
                    if i == len(section_titles) - 1:
                        chunk = body[idx:]
                    else:
                        chunk = body[idx:idx + chunk_size]
                    idx += chunk_size
                    rebuilt.append(title)
                    rebuilt.append('\n\n'.join(chunk))
                text = '\n\n'.join([x for x in rebuilt if x and x.strip()])

        return text.strip()

    def _insert_images_into_content(self, content, images):
        """Chèn hình ảnh vào giữa các section trong content
        
        Args:
            content: Nội dung bài viết (có thể có ## headers)
            images: List các dict {'url': ..., 'caption': ...}
        
        Returns:
            Content đã được chèn hình ảnh
        """
        if not images or not content:
            return content
        
        import re
        
        # Tìm tất cả các ## headers (markdown h2) ở đầu dòng
        sections = re.split(r'(?m)(^##[^\n]+)', content)
        
        if len(sections) <= 1:
            # Không có section, chèn ảnh ở giữa content
            paragraphs = content.split('\n\n')
            if len(paragraphs) > 2:
                mid = len(paragraphs) // 2
                img_html = self._format_image_html(images[0])
                paragraphs.insert(mid, img_html)
                return '\n\n'.join(paragraphs)
            return content
        
        # Có sections, chèn ảnh sau mỗi section (tối đa 3 ảnh)
        result = []
        img_idx = 0
        
        for i, part in enumerate(sections):
            result.append(part)
            
            # Nếu đây là header section (##) và tiếp theo là content
            if part.strip().startswith('##') and img_idx < len(images) and img_idx < 3:
                # Chèn ảnh sau section content (phần tiếp theo)
                if i + 1 < len(sections):
                    # Thêm ảnh vào cuối phần content của section này
                    next_content = sections[i + 1] if i + 1 < len(sections) else ''
                    # Chỉ chèn nếu có đủ content
                    if len(next_content.strip()) > 100:
                        img_html = self._format_image_html(images[img_idx])
                        # Sẽ chèn ảnh ở cuối section trong vòng lặp tiếp theo
                        img_idx += 1
            
            # Chèn ảnh sau mỗi block content của section
            elif not part.strip().startswith('##') and part.strip() and img_idx > 0:
                # Đã có ảnh được đánh dấu ở iteration trước
                pass
        
        # Cách tiếp cận đơn giản hơn: chèn ảnh sau mỗi section
        result_parts = []
        img_idx = 0
        for i, part in enumerate(sections):
            result_parts.append(part)
            # Sau mỗi phần content (không phải header), chèn ảnh
            if not part.strip().startswith('##') and part.strip() and len(part.strip()) > 150:
                if img_idx < len(images) and img_idx < 3:
                    img_html = self._format_image_html(images[img_idx])
                    result_parts.append(f'\n\n{img_html}\n\n')
                    img_idx += 1
        
        return '\n'.join(result_parts)
    
    def _format_image_html(self, image):
        """Format một hình ảnh thành HTML với style đẹp"""
        url = image.get('url', '') if isinstance(image, dict) else image
        caption = image.get('caption', '') if isinstance(image, dict) else ''
        
        html = f'''<figure style="margin: 2rem 0; text-align: center;">
    <img src="{url}" alt="{caption}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" onerror="this.style.display='none'">
    {f'<figcaption style="margin-top: 0.5rem; font-size: 0.9rem; color: #666; font-style: italic;">{caption}</figcaption>' if caption else ''}
</figure>'''
        return html

    def _parse_magazine_article(self, raw_text, topic, keywords, description='', image_url=''):
        """Parse chuỗi raw từ Groq thành dict bài viết"""
        # Xử lý cả format **TITLE:** và TITLE:
        # Với prompt mới, raw_text chính là content. Các trường khác sẽ được tạo riêng.
        import re
        
        # Content gốc từ AI
        raw = (raw_text or "").strip()

        # 1) Làm sạch: bỏ heading và các dòng tiêu đề cũ
        banned_prefixes = [
            "ứng dụng thực tiễn",
            "tầm quan trọng của",
            "góc nhìn chiến lược",
            "khuyến nghị cho người đọc",
            "lợi ích và thách thức",
            "xu hướng phát triển",
            "kinh nghiệm từ chuyên gia",
        ]

        cleaned_lines = []
        for ln in raw.split('\n'):
            line = ln.strip()
            if not line:
                continue
            # Bỏ markdown heading
            if line.startswith('#'):
                continue
            norm = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", line.lower())).strip()
            if any(norm.startswith(p) for p in banned_prefixes):
                continue
            cleaned_lines.append(line)

        flat_text = " ".join(cleaned_lines).strip()

        # 2) Tách câu
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat_text) if s.strip()]

        # 3) Tiêu đề: lấy 2–3 câu đầu
        if sentences:
            title_sentences = sentences[:3]
            title = " ".join(title_sentences)
        else:
            desc_clean = (description or '').strip()
            if desc_clean:
                title = desc_clean
            elif topic:
                title = str(topic)
            else:
                title = "Bài viết từ AI"

        # 4) Tóm tắt: mô tả tạp chí hoặc 1–2 câu tiếp theo
        desc_clean = (description or '').strip()
        if desc_clean:
            short_desc = re.sub(r"\s+", " ", desc_clean)[:220]
            summary = short_desc
        elif len(sentences) > 3:
            summary = " ".join(sentences[3:5])
        else:
            summary = "Bài viết do AI tổng hợp và viết lại từ nhiều nguồn tin tức."

        # 5) Chia lại nội dung thành đúng 3 đoạn văn
        if sentences:
            total = len(sentences)
            per_block = max(1, total // 3)
            paras = []
            start = 0
            for i in range(3):
                if start >= total:
                    break
                end = total if i == 2 else min(total, start + per_block)
                block = " ".join(sentences[start:end]).strip()
                if block:
                    paras.append(block)
                start = end
            content = "\n\n".join(paras)
        else:
            content = flat_text
        
        # Vì không còn yêu cầu AI trả về IMAGE_KEYWORDS_EN, ta tạo fallback
        final_image_url = image_url or self._fallback_image_url(title)

        return {
            'title':     title,
            'summary':   summary,
            'content':   content,
            'keywords':  keywords,
            'topic':     topic,
            'image_url': final_image_url,
            'all_images': [final_image_url] if final_image_url else []
        }

    def _fallback_magazine_article(self, topic, keywords, angle, image_url=''):
        """Bài viết mẫu khi Groq không khả dụng - đa dạng hóa"""
        import random
        import time
        
        # Ưu tiên ảnh có nguồn từ Wikimedia; nếu không có mới dùng picsum
        random_seed = int(time.time()) + random.randint(1000, 9999)
        image_source_url = ''
        if not image_url:
            wiki_image, wiki_source = self._fetch_wikimedia_image(topic, keywords)
            if wiki_image:
                image_url = wiki_image
                image_source_url = wiki_source
            else:
                image_url = self._fallback_image_url(f"{topic}-{random_seed}")
        
        # Tạo tiêu đề đa dạng nhưng tránh các cụm sáo rỗng
        title_templates = [
            f"{topic}: Bức tranh toàn cảnh hiện tại",
            f"Diễn biến mới về {topic} và những điểm đáng chú ý",
            f"{topic} hôm nay và câu chuyện đằng sau các con số",
            f"{topic} dưới góc nhìn thực tế và tác động đến đời sống",
        ]
        title = random.choice(title_templates) if topic else (angle or "Bài viết từ AI")

        # Summary ngắn gọn 1–2 câu
        summary = (
            f"Bài viết tổng hợp và phân tích các thông tin mới nhất về {topic}, "
            f"giúp người đọc hiểu rõ bối cảnh, nguyên nhân và tác động thực tế."
            if topic else
            "Bài viết do AI tổng hợp và phân tích từ nhiều nguồn tin tức."
        )

        # Nội dung fallback: 3 đoạn nghị luận, không heading
        intro_templates = [
            f"Trong bối cảnh hiện nay, {topic} đang trở thành một trong những chủ đề được quan tâm nhiều nhất. "
            f"Những biến động liên tục về chính sách, thị trường và đời sống xã hội khiến người đọc cần một bức tranh tổng thể, "
            f"không chỉ dừng ở các con số rời rạc mà còn là câu chuyện đằng sau chúng.",
            f"{topic} không còn là khái niệm xa lạ mà gắn chặt với các quyết định hằng ngày của doanh nghiệp và người dân. "
            f"Việc hiểu đúng bản chất vấn đề, thay vì chỉ chạy theo các tin tức giật gân, giúp người đọc có cái nhìn tỉnh táo và dài hạn hơn.",
        ]

        body_templates = [
            f"Nếu nhìn sâu vào các số liệu và xu hướng liên quan đến {topic}, có thể thấy bức tranh phức tạp hơn nhiều so với những gì xuất hiện trên các tiêu đề ngắn. "
            f"Mỗi con số tăng hay giảm đều gắn với những quyết định cụ thể của nhà hoạch định chính sách, doanh nghiệp và người tiêu dùng. "
            f"Khi ghép nối các mảnh ghép đó lại, chúng ta sẽ nhận ra các mô hình lặp lại, những sai lầm thường gặp và cả các cơ hội ít được nhắc tới trong dòng tin tức dày đặc.",
            f"Ở chiều ngược lại, phản ứng của thị trường và cộng đồng trước các thay đổi liên quan đến {topic} cũng cho thấy mức độ nhạy cảm của tâm lý đám đông. "
            f"Nhiều quyết định vội vàng, thiếu thông tin toàn diện có thể dẫn tới những hệ quả dây chuyền, trong khi những lựa chọn bình tĩnh, dựa trên phân tích dữ kiện thường mang lại kết quả bền vững hơn.",
        ]

        conclusion_templates = [
            f"Từ những phân tích trên, có thể thấy {topic} không chỉ là tập hợp các tin tức ngắn hạn mà là câu chuyện dài hơi về cách xã hội thích ứng với thay đổi. "
            f"Người đọc nếu biết chọn lọc nguồn tin, ưu tiên những bài viết có luận điểm rõ ràng và dữ kiện kiểm chứng được, sẽ có khả năng đưa ra quyết định sáng suốt hơn trong công việc lẫn đời sống.",
            f"Cuối cùng, điều quan trọng không phải là chạy theo mọi biến động liên quan tới {topic}, mà là hiểu được logic phía sau chúng. "
            f"Khi nắm được bức tranh tổng thể và biết đặt từng thông tin vào đúng ngữ cảnh, mỗi người sẽ chủ động hơn thay vì bị cuốn theo làn sóng tin tức.",
        ]

        p1 = random.choice(intro_templates)
        p2 = random.choice(body_templates)
        p3 = random.choice(conclusion_templates)

        content = "\n\n".join([p1, p2, p3])

        # Tiêu đề dài 2–3 câu: lấy 2–3 câu đầu từ content
        import re
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", content) if s.strip()]
        if sentences:
            title = " ".join(sentences[:3])

        source_urls = [image_source_url] if image_source_url else []
        return {
            'title':     title,
            'summary':   summary,
            'content':   content,
            'keywords':  keywords,
            'topic':     topic,
            'image_url': image_url,
            'all_images': [image_url] if image_url else [],
            'source_urls': source_urls
        }


# ----------------------------------
# Test Function
# ----------------------------------
if __name__ == "__main__":
    generator = SimpleArticleGenerator()
    
    result = generator.generate_article(
        user_id=1,
        topic="Trí Tuệ Nhân Tạo",
        description="Tìm hiểu về xu hướng AI hiện nay",
        keywords="trí tuệ nhân tạo ChatGPT",
        max_sources=3
    )
    
    if result['success']:
        print("\n" + "=" * 70)
        print("GENERATED ARTICLE:")
        print("=" * 70)
        print(f"Title: {result['article']['title']}")
        print(f"Summary: {result['article']['summary']}")
        print(f"\nContent:\n{result['article']['content'][:500]}...")
