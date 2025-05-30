import newspaper

from search_gov_crawler.elasticsearch.i14y_helper import (
    ALLOWED_LANGUAGE_CODE,
    current_utc_iso,
    detect_lang,
    generate_url_sha256,
    get_base_extension,
    get_domain_name,
    get_url_path,
    parse_date_safely,
    summarize_text,
)
from search_gov_crawler.elasticsearch.parse_html_scrapy import convert_html_scrapy
from search_gov_crawler.search_gov_spiders.helpers import content, encoding


def convert_html(response_bytes: bytes, url: str, response_language: str = None):
    """Extracts and processes article content from HTML using newspaper4k."""
    html_content = encoding.decode_http_response(response_bytes=response_bytes)
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
    tags = article.tags or article.keywords or article.meta_keywords or article_backup["keywords"] or None

    time_now_str = current_utc_iso()
    path = article.url or article_backup["url"] or url

    basename, extension = get_base_extension(url)
    sha_id = generate_url_sha256(path)

    language = article.meta_lang or article_backup["language"] or response_language or detect_lang(main_content)
    language = language[:2] if language else None
    valid_language = f"_{language}" if language in ALLOWED_LANGUAGE_CODE else ""

    # Only run summarize text if either tags or description is not populated
    if not (tags and description):
        summary, keywords = summarize_text(text=main_content, url=url, lang_code=language)
        tags = tags or keywords
        description = description or summary

    return {
        "audience": article_backup["audience"],
        "changed": parse_date_safely(article_backup["changed"]),
        "click_count": None,
        "content_type": "article",
        "created_at": parse_date_safely(article_backup["created_at"]) or time_now_str,
        "created": None,
        "_id": sha_id,
        "id": sha_id,
        "thumbnail_url": article_backup["thumbnail_url"] or None,
        "language": language,
        "mime_type": "text/html",
        "path": path,
        "promote": None,
        "searchgov_custom1": None,
        "searchgov_custom2": None,
        "searchgov_custom3": None,
        "tags": tags,
        "updated_at": time_now_str,
        "updated": parse_date_safely(article.publish_date) or parse_date_safely(article_backup["created_at"]),
        f"title{valid_language}": title,
        f"description{valid_language}": content.sanitize_text(description),
        f"content{valid_language}": content.sanitize_text(main_content),
        "basename": basename,
        "extension": extension or None,
        "url_path": get_url_path(url),
        "domain_name": get_domain_name(url),
    }
