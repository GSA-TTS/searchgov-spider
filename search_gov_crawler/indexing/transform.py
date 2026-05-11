import logging
from io import BytesIO

import newspaper
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from search_gov_crawler.indexing import helpers
from search_gov_crawler.indexing.parse import convert_html_scrapy, get_pdf_links, get_pdf_meta, get_pdf_text
from search_gov_crawler.search_gov_spiders.helpers import content, encoding

log = logging.getLogger(__name__)

# Suppress overly verbose pypdf logging
logging.getLogger("pypdf._reader").setLevel(logging.ERROR)
logging.getLogger("pypdf._cmap").setLevel(logging.CRITICAL)


def set_default_metadata_fields() -> dict:
    """These fields are placeholders for fields populated at runtime"""
    return {
        "do_not_delete": False,
        "document_source": None,
        "download_size": None,
        "download_time": None,
        "keep_until": None,
    }


def convert_html(response_bytes: bytes, url: str, response_language: str | None = None):
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

    title = article_backup["title"] or article.title or article.meta_site_name or None
    description = article.meta_description or article.summary or article_backup["description"] or None
    tags = article.tags or article.keywords or article.meta_keywords or article_backup["keywords"] or None

    time_now_str = helpers.current_utc_iso()
    path = article.url or article_backup["url"] or url

    basename, extension, _ = helpers.get_base_extension(url)
    sha_id = helpers.generate_url_sha256(path)

    language = article.meta_lang or article_backup["language"] or response_language or helpers.detect_lang(main_content)
    language = language[:2] if language else None
    valid_language = f"_{language}" if language in helpers.ALLOWED_LANGUAGE_CODE else ""

    # Only run summarize text if either tags or description is not populated
    if not (tags and description):
        summary, keywords = helpers.summarize_text(text=main_content, url=url, lang_code=language)
        tags = tags or keywords
        description = description or summary

    return {
        "audience": article_backup["audience"],
        "changed": helpers.parse_dates_safely(article_backup["changed"]),
        "click_count": None,
        "content_type": "article",
        "created_at": helpers.parse_dates_safely(article_backup["created_at"]) or time_now_str,
        "created": None,
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
        "updated": helpers.parse_dates_safely(article.publish_date, article_backup["created_at"]),
        f"title{valid_language}": title,
        f"description{valid_language}": content.sanitize_text(str(description)),
        f"content{valid_language}": content.sanitize_text(main_content),
        "basename": basename,
        "extension": extension or None,
        "url_path": helpers.get_url_path(url),
        "domain_name": helpers.get_domain_name(url),
        "dap_domain_visits_count": None,
    }


def add_title_and_filename(original_value: str, title: str, filename: str) -> str:
    """
    Adds PDF's title and file name to the provided value. Used mainly to improve index and relevance.

    Args:
        original_value: str The value to use to apply the change, eg "content"
        title: str The title to add to the original value
        filename: str the filename to add to the original value

    Returns:
        the new value
    """

    return f"{title} {filename} {original_value}"


def convert_pdf(response_bytes: bytes, url: str, response_language: str | None = None):
    """Extracts and processes PDF content using pypdf."""
    log.debug("Processing PDF content from %s", url)

    pdf_stream = BytesIO(response_bytes)
    try:
        reader = PdfReader(pdf_stream)
    except PdfReadError as err:
        log.warning("Could not download PDF file at %s: %s", url, err)
        return None

    try:
        meta_values = get_pdf_meta(reader)
        main_content, pages = get_pdf_text(reader)
    except FileNotDecryptedError as err:
        log.warning("Could not decrypt PDF file at %s: %s", url, err)
        return None

    time_now_str = helpers.current_utc_iso()
    basename, extension, filename = helpers.get_base_extension(url)

    title_value = meta_values.get("Title") or helpers.separate_file_name(filename)
    main_content = main_content or title_value
    language = meta_values.get("Lang") or response_language or helpers.detect_lang(main_content)
    language = language[:2] if language else None

    description, keywords = helpers.summarize_text(text=main_content, url=url, lang_code=language)

    # name and populate language-aware fields
    valid_language = f"_{language}" if language in helpers.ALLOWED_LANGUAGE_CODE else ""
    title_key = f"title{valid_language}"

    content_key = f"content{valid_language}"
    content_value = add_title_and_filename(
        original_value=f"{content.sanitize_text(main_content)} {' '.join(get_pdf_links(pages))}",
        title=title_value,
        filename=filename,
    )

    description_key = f"description{valid_language}"
    description_value = add_title_and_filename(
        original_value=str(content.sanitize_text(str(description))),
        title=title_value,
        filename=filename,
    )

    return {
        "audience": None,
        "changed": helpers.parse_dates_safely(meta_values.get("ModDate"), meta_values.get("SourceModified")),
        "click_count": None,
        "content_type": None,
        "created_at": helpers.parse_dates_safely(meta_values.get("CreationDate")) or time_now_str,
        "created": None,
        "id": helpers.generate_url_sha256(url),
        "thumbnail_url": None,
        "language": language,
        "mime_type": "application/pdf",
        "path": url,
        "promote": None,
        "searchgov_custom1": None,
        "searchgov_custom2": None,
        "searchgov_custom3": None,
        "tags": keywords,
        "updated_at": time_now_str,
        "updated": helpers.parse_dates_safely(meta_values.get("CreationDate")),
        title_key: title_value,
        description_key: description_value,
        content_key: content_value,
        "basename": basename,
        "extension": extension or None,
        "url_path": helpers.get_url_path(url),
        "domain_name": helpers.get_domain_name(url),
        # fields populated at runtime, placeholders here
        "dap_domain_visits_count": None,
        "metadata": set_default_metadata_fields(),
    }
