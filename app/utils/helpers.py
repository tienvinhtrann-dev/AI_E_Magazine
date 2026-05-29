"""
Utility helper functions shared across routes.
"""
import re
import json
import unicodedata
from database.db_simple import get_connection
from database.magazine_model_simple import get_magazine_by_id, get_articles_by_magazine


# ------------------------------------------------------------------
# JSON filter (also registered as Jinja2 template filter in app/__init__.py)
# ------------------------------------------------------------------

def fromjson_filter(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []


# ------------------------------------------------------------------
# Slug generation
# ------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert a title into a URL-friendly slug, with proper Vietnamese support."""
    if not text:
        return "tap-chi-ai"
    s = str(text)
    # Replace Vietnamese-specific characters that don't decompose via NFKD
    _VN_SPECIAL = {
        'đ': 'd', 'Đ': 'd',
        'ơ': 'o', 'Ơ': 'o',
        'ư': 'u', 'Ư': 'u',
    }
    for vn_char, replacement in _VN_SPECIAL.items():
        s = s.replace(vn_char, replacement)
    # Now apply NFKD to remove the remaining combining accents (á→a, etc.)
    norm = unicodedata.normalize("NFKD", s)
    without_accents = "".join(ch for ch in norm if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", without_accents)
    slug = slug.strip("-").lower()
    return slug or "tap-chi-ai"


# ------------------------------------------------------------------
# Magazine category count sync
# ------------------------------------------------------------------

def _refresh_magazine_category_counts(magazine_id: int):
    """Sync article_count in categories_config with actual DB counts."""
    try:
        magazine = get_magazine_by_id(magazine_id)
        if not magazine:
            return
        raw = magazine.get('categories_config')
        if not raw:
            return
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return
        configured_names = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name', '')).strip()
            if name:
                configured_names.append(name)
        if not configured_names:
            return
        configured_index = {name.lower(): name for name in configured_names}

        def _resolve(topic_name):
            name = (topic_name or '').strip()
            if not name:
                return ''
            key = name.lower()
            if key in configured_index:
                return configured_index[key]
            matches = [cfg for cfg in configured_names if cfg.lower() in key or key in cfg.lower()]
            return matches[0] if matches else name

        counts = {}
        for article in get_articles_by_magazine(magazine_id):
            resolved = _resolve(article.get('topic'))
            if not resolved:
                continue
            key = resolved.lower()
            counts[key] = counts.get(key, 0) + 1

        for item in parsed:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name', '')).strip()
            if not name:
                continue
            item['article_count'] = counts.get(name.lower(), 0)

        conn = get_connection()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE magazines SET categories_config = %s WHERE id = %s",
                (json.dumps(parsed, ensure_ascii=False), magazine_id)
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            if conn:
                conn.close()
    except Exception:
        return


# ------------------------------------------------------------------
# Article content display helpers
# ------------------------------------------------------------------

def _dedupe_article_content_for_display(content):
    """Remove duplicate headings/paragraphs for clean article display."""
    if not content or not isinstance(content, str):
        return content
    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
    unique_blocks = []
    seen_norm = set()
    seen_headings = set()
    for block in blocks:
        normalized = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', block.lower())).strip()
        if not normalized:
            continue
        is_heading = block.strip().startswith('##')
        if is_heading:
            if normalized in seen_headings:
                continue
            seen_headings.add(normalized)
        if normalized in seen_norm:
            continue
        near_dup = False
        for old in seen_norm:
            if len(normalized) > 80 and (normalized in old or old in normalized):
                near_dup = True
                break
        if near_dup:
            continue
        seen_norm.add(normalized)
        unique_blocks.append(block)
    return '\n\n'.join(unique_blocks)


def _limit_article_sections_for_display(content, max_sections=5):
    """Limit the number of ## heading sections displayed."""
    if not content or not isinstance(content, str):
        return content
    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
    if not blocks:
        return content
    result = []
    section_count = 0
    for block in blocks:
        is_heading = block.strip().startswith('##')
        if is_heading:
            if section_count >= max_sections:
                break
            section_count += 1
        result.append(block)
    return '\n\n'.join(result)


# ------------------------------------------------------------------
# Magazine creation helpers
# ------------------------------------------------------------------

def _derive_topic_keywords_from_description(description_text, default_topic, default_keywords=""):
    """
    Extract topic and keywords from a unified description field.
    Supports the pattern: "... Từ khóa: a, b, c"
    """
    if not isinstance(description_text, str):
        return default_topic, (default_keywords or default_topic), description_text
    text = description_text.strip()
    if not text:
        return default_topic, (default_keywords or default_topic), text
    lower = text.lower()
    kw_idx = lower.find('từ khóa')
    if kw_idx == -1:
        kw_idx = lower.find('tu khoa')
    keywords = default_keywords or ""
    description_clean = text
    if kw_idx != -1:
        before = text[:kw_idx].strip()
        after = text[kw_idx:]
        parts = after.split(':', 1)
        after_payload = parts[1] if len(parts) > 1 else ''
        stop = len(after_payload)
        for sep in ['\n', '.', ';']:
            pos = after_payload.find(sep)
            if pos != -1:
                stop = min(stop, pos)
        kw_str = after_payload[:stop].strip().strip(',;.')
        if kw_str:
            keywords = kw_str
        description_clean = before or text
    topic = default_topic or ""
    if description_clean:
        first_sentence = description_clean.split('.')[0].strip()
        if len(first_sentence) > 0:
            topic = first_sentence
    if not topic:
        topic = default_topic
    if not keywords:
        keywords = topic or default_topic
    return topic, keywords, description_clean
