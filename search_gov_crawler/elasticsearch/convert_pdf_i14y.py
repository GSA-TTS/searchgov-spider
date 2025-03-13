import re
from io import BytesIO
from pypdf import PdfReader
from datetime import UTC, datetime, timedelta
from search_gov_crawler.search_gov_spiders.helpers import content
from search_gov_crawler.elasticsearch.i14y_helper import ALLOWED_LANGUAGE_CODE, null_date, \
    get_url_path, get_base_extension, current_utc_iso, generate_url_sha256, get_domain_name, \
    summarize_text, separate_file_name, detect_lang


def convert_pdf(response_bytes: bytes, url: str, response_language: str = None):
    """Extracts and processes PDF content using pypdf."""
    pdf_stream = BytesIO(response_bytes)
    reader = PdfReader(pdf_stream)

    if reader.is_encrypted:
        return None

    meta_values = get_pdf_meta(reader)
    
    basename, extension = get_base_extension(url)
    title = meta_values.get("Title") or separate_file_name(f"{basename}.{extension}")
    main_content = get_pdf_text(reader) or title

    sha_id = generate_url_sha256(url)

    language = meta_values.get("Lang") or response_language or detect_lang(main_content)
    language = language[:2] if language else None
    valid_language = f"_{language}" if language in ALLOWED_LANGUAGE_CODE else ""
    
    description, keywords = summarize_text(text=main_content, lang_code=language)

    time_now_str = current_utc_iso()

    return  {
        "audience": None,
        "changed": null_date(meta_values.get("ModDate") or meta_values.get("SourceModified")),
        "click_count": None,
        "content_type": None,
        "created_at": null_date(meta_values.get("CreationDate")) or time_now_str,
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
        "updated": null_date(meta_values.get("CreationDate")),
        f"title{valid_language}": title,
        f"description{valid_language}": content.sanitize_text(description),
        f"content{valid_language}": content.sanitize_text(main_content),
        "basename": basename,
        "extension": extension or None,
        "url_path": get_url_path(url),
        "domain_name": get_domain_name(url),
    }
    

def get_pdf_text(reader: PdfReader) -> str:
    """
    Returns clean text/content from all pdf pages

    Args:
        reader: PdfReader from pypdf

    Returns:
        (string) without new any special characters
    """
    text = ""
    for page in reader.pages:
        text += page.extract_text() + " "
    return text


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

    date_string = value[2:] # Remove the "D:" prefix

    """
    Example of matched date values:
        "D:20191018122555-04'00'"
        "D:20191018162538"
    """
    match = re.match(r"(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?([+-]\d{2})?'?(\d{2})?'?", date_string)

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
            if match.group(7) and apply_tz_offset: # handle timezone offset if matched
                tz_sign = 1 if tz_hour >= 0 else -1
                tz_offset = timedelta(hours=tz_hour, minutes=tz_minute)
                dt = dt - tz_sign * tz_offset
            return dt
        except ValueError as err:
            raise f"Failed to parse Date value \"{value}\":\n{str(err)}"
    return content.sanitize_text(value)
