import re
from io import BytesIO
from pypdf import PdfReader, PageObject
from typing import Tuple
from datetime import UTC, datetime, timedelta
from search_gov_crawler.search_gov_spiders.helpers import content
from search_gov_crawler.elasticsearch.i14y_helper import (
    ALLOWED_LANGUAGE_CODE,
    parse_date_safely,
    get_url_path,
    get_base_extension,
    current_utc_iso,
    generate_url_sha256,
    get_domain_name,
    summarize_text,
    separate_file_name,
    detect_lang,
)


def add_title_and_filename(key: str, title_key: str, doc: dict):
    """
    Adds PDF's title and file name to the provided key.
    Used mainly to improve index and relevance.

    Args:
        key: str The key to use to apply the change, eg "content"
        doc: dict The i14y document the changes will be applied to

    Returns:
        None The changes are applied to the document as a referance/pointer
    """
    doc[key] = f"{doc[title_key]} {doc['basename']}.{doc['extension']} {doc[key]}"


def get_links_set(pages: list[Tuple[str, PageObject]]):
    """
    Returns a set of links for all pages in the PDF

    Args:
        reader: PdfReader from pypdf

    Returns:
        (list[str]) unique set of links
    """
    key = "/Annots"
    uri = "/URI"
    ank = "/A"
    links = {}

    for page_item in pages:
        text, page = page_item
        page_links = re.findall(r"https?://\S+|www\.\S+", text)
        # Get all visible links
        for link in page_links:
            links[link] = link

        # Get all hidden links
        page_object = page.get_object()
        if key in page_object.keys():
            ann = page_object[key]
            for a in ann:
                u = a.get_object()
                if uri in u[ank].keys():
                    link = u[ank][uri]
                    links[link] = link
    return links.values()


def convert_pdf(response_bytes: bytes, url: str, response_language: str = None):
    """Extracts and processes PDF content using pypdf."""
    pdf_stream = BytesIO(response_bytes)
    reader = PdfReader(pdf_stream)

    if reader.is_encrypted:
        return None

    meta_values = get_pdf_meta(reader)

    basename, extension = get_base_extension(url)
    title = meta_values.get("Title") or separate_file_name(f"{basename}.{extension}")
    main_content, pages = get_pdf_text(reader)
    main_content = main_content or title

    sha_id = generate_url_sha256(url)

    language = meta_values.get("Lang") or response_language or detect_lang(main_content)
    language = language[:2] if language else None
    valid_language = f"_{language}" if language in ALLOWED_LANGUAGE_CODE else ""

    description, keywords = summarize_text(text=main_content, lang_code=language)

    time_now_str = current_utc_iso()

    content_key = f"content{valid_language}"
    description_key = f"description{valid_language}"
    title_key = f"title{valid_language}"

    i14y_doc = {
        "audience": None,
        "changed": parse_date_safely(meta_values.get("ModDate") or meta_values.get("SourceModified")),
        "click_count": None,
        "content_type": None,
        "created_at": parse_date_safely(meta_values.get("CreationDate")) or time_now_str,
        "created": None,
        "_id": sha_id,
        "id": sha_id,
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
        "updated": parse_date_safely(meta_values.get("CreationDate")),
        title_key: title,
        description_key: content.sanitize_text(description),
        content_key: content.sanitize_text(main_content),
        "basename": basename,
        "extension": extension or None,
        "url_path": get_url_path(url),
        "domain_name": get_domain_name(url),
    }

    add_title_and_filename(content_key, title_key, i14y_doc)
    add_title_and_filename(description_key, title_key, i14y_doc)
    all_links = get_links_set(pages)
    i14y_doc[content_key] = f"{i14y_doc[content_key]} {' '.join(all_links) if len(all_links) > 0 else ''}"

    return i14y_doc


def get_pdf_text(reader: PdfReader) -> Tuple[str, list[Tuple[str, PageObject]]]:
    """
    Returns clean text/content from all pdf pages

    Args:
        reader: PdfReader from pypdf

    Returns:
        (string) without new any special characters
    """
    text = ""
    pages = []
    for page in reader.pages:
        page_text = page.extract_text()
        text += page_text + " "
        pages.append((page_text, page))
    return (text, pages)


def get_pdf_meta(reader: PdfReader):
    """
    Returns pdf metadata

    Args:
        reader: PdfReader from pypdf

    Returns:
        metadata object with possible keys: https://exiftool.org/TagNames/PDF.html
    """
    clean_metadata = {}
    metadata: dict = dict(reader.metadata)
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            new_key = None
            if key.startswith("/"):
                new_key = key[1:]
            new_key = new_key or key
            clean_metadata[new_key] = parse_if_date(value)
    return clean_metadata


def parse_if_date(value, apply_tz_offset: bool = False):
    """
    Parses a value as date if matched the conventional pdf/exif date format. If parsing fails,
    returns the original value

    Args:
        value: The value to parse.

    Returns:
        A datetime.datetime object if parsing is successful, otherwise the original value.
    """
    if not isinstance(value, str) or not value.startswith("D:"):
        return content.sanitize_text(value)

    date_string = value[2:]  # Remove the "D:" prefix

    """
    Example of matched date values:
        "D:20191018122555-04'00'"
        "D:20191018162538"
    """
    match = re.match(
        r"(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?([+-]\d{2})?'?(\d{2})?'?",
        date_string,
    )

    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4)) if match.group(4) else 0
        minute = int(match.group(5)) if match.group(5) else 0
        second = int(match.group(6)) if match.group(6) else 0
        tz_hour = int(match.group(7)[:3]) if match.group(7) else 0
        tz_minute = int(match.group(7)[4:]) if match.group(7) and len(match.group(7)) > 4 else 0

        try:
            dt = datetime(year, month, day, hour, minute, second)
            if match.group(7) and apply_tz_offset:  # handle timezone offset if matched
                tz_sign = 1 if tz_hour >= 0 else -1
                tz_offset = timedelta(hours=tz_hour, minutes=tz_minute)
                dt = dt - tz_sign * tz_offset
            return dt
        except ValueError as err:
            raise f'Failed to parse Date value "{value}":\n{str(err)}'
    return content.sanitize_text(value)
