import hashlib
import os
from datetime import UTC, datetime
from urllib.parse import urlparse

import newspaper
from datetime import datetime, timezone
from urllib.parse import urlparse

from search_gov_crawler.elasticsearch.parse_html_scrapy import convert_html_scrapy
from search_gov_crawler.search_gov_spiders.helpers import content

# fmt: off
ALLOWED_LANGUAGE_CODE = (
    "ar", "bg", "bn", "ca", "cs", "da", "de", "el", "en", "es", "et", "fa", "fr",
    "he", "hi", "hr", "ht", "hu", "hy", "id", "it", "ja", "km", "ko", "lt", "lv",
    "mk", "nl", "pl", "ps", "pt", "ro", "ru", "sk", "so", "sq", "sr", "sw", "th",
    "tr", "uk", "ur", "uz", "vi", "zh",
)
# fmt: on

def checkDate(article_date):
    if article_date != "": 
        return article_date
    else:
        return None 
    
def convert_html(html_content: str, url: str):
    """Extracts and processes article content from HTML using newspaper4k."""
    config = newspaper.Config()
    config.fetch_images = False  # we are not using images, do not fetch!
    config.clean_article_html = False  # we are not using article_html, so don't clean it!
    article = newspaper.Article(url=url, config=config)
    article.download(input_html=html_content)
    article.parse()
    article.nlp()

    article_backup = convert_html_scrapy(html_content=html_content)
    main_content = article.text or article_backup["content"]

    if not main_content:
        return None

    title = article.title or article.meta_site_name or article_backup["title"] or None
    description = article.meta_description or article.summary or article_backup["description"] or None

    time_now_str = current_utc_iso()
    path = article.url or article_backup["url"] or url

    basename, extension = get_base_extension(url)
    sha_id = generate_url_sha256(path)

    language = article.meta_lang or article_backup["language"]
    valid_language = f"_{language}" if language in ALLOWED_LANGUAGE_CODE else ""

    return {
        "audience": article_backup["audience"],
        "changed": checkDate(article_backup["changed"]),
        "click_count": None,
        "content_type": "article",
        "created_at": checkDate(article_backup["created_at"]) or time_now_str,
        "created": None,
        "_id": sha_id,
        "id": sha_id,
        "thumbnail_url": article.meta_img or article.top_image or article_backup["thumbnail_url"] or None,
        "language": article.meta_lang,
        "mime_type": "text/html",
        "path": path,
        "promote": None,
        "searchgov_custom1": None,
        "searchgov_custom2": None,
        "searchgov_custom3": None,
        "tags": article.tags or article.keywords or article.meta_keywords or article_backup["keywords"],
        "updated_at": time_now_str,
        "updated": checkDate(article.publish_date) or checkDate(article_backup["created_at"]),
        f"title{valid_language}": title,
        f"description{valid_language}": content.sanitize_text(description),
        f"content{valid_language}": content.sanitize_text(main_content),
        "basename": basename,
        "extension": extension or None,
        "url_path": get_url_path(url),
        "domain_name": get_domain_name(url),
    }


def ensure_http_prefix(url: str):
    return url if url.startswith(("http://", "https://")) else f"https://{url}"

def get_url_path(url: str) -> str:
    """Extracts the path from a URL."""
    url = ensure_http_prefix(url)
    return urlparse(url).path


def get_base_extension(url: str) -> tuple[str, str]:
    """Extracts the basename and file extension from a URL."""
    url = ensure_http_prefix(url)
    basename, extension = os.path.splitext(os.path.basename(urlparse(url).path))
    return basename, extension


def current_utc_iso() -> str:
    """Returns the current UTC timestamp in ISO format."""
    return datetime.now(tz=UTC).isoformat(timespec="milliseconds") + "Z"


def generate_url_sha256(url: str) -> str:
    """Generates a SHA-256 hash for a given URL."""
    url = ensure_http_prefix(url)
    return hashlib.sha256(url.encode()).hexdigest()


def get_domain_name(url: str) -> str:
    """Extracts the domain from a URL, support www (only if the url was parsed with it) ensuring consistency."""
    url = ensure_http_prefix(url)
    parsed = urlparse(url)
    return parsed.netloc
