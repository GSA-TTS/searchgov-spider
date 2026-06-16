import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from pypdf import PageObject, PdfReader
from pypdf.generic import IndirectObject
from scrapy import Selector

from search_gov_crawler.search_gov_spiders.helpers import content

log = logging.getLogger(__name__)


def extract_article_content(html_selector: Selector) -> str:
    """
    Extracts the main content from an article in HTML while excluding links, button text, etc,
    and ignoring <style> and <script> tags.

    :param html_selector: Scrapy HTML content selector.
    :return: The extracted content as a string.
    """

    body = html_selector.css("body")

    if not body:
        return ""

    content_text = body.xpath(
        ".//text()[not(ancestor::a) and not(ancestor::button) and not(ancestor::style) and not(ancestor::script)]",
    ).getall()

    content_text = " ".join(text.strip() for text in content_text if text.strip())
    return content.replace_whitespace(content_text)


def get_html_meta(html_selector: Selector, meta_names: list) -> dict:
    """
    Extracts meta tag values by their name or property attributes and returns a dictionary.

    :param html_selector: Scrapy HTML content selector.
    :param meta_names: A list of meta tag names/properties to extract values for.
    :return: A dictionary with meta names as keys and extracted values or None.
    """
    meta_values = {}

    for name in meta_names:
        value = html_selector.xpath(f'//meta[@content and (@name="{name}" or @property="{name}")]/@content').get()
        meta_values[name] = value or None

    return meta_values


def convert_html_scrapy(html_content: str) -> dict:
    """
    Converts HTML content into a dictionary of extracted values for indexing in opensearch.
    """

    return_obj = {}
    html_selector = Selector(text=html_content)

    meta_tags = get_html_meta(
        html_selector,
        [
            "keywords",
            "description",
            "summary",
            "date",
            "revised",
            "audience",
            "pagename",
            "language",
            "url",
            "og:title",
            "og:image",
            "og:site_name",
            "og:description",
        ],
    )

    return_obj["audience"] = meta_tags["audience"]
    return_obj["title"] = (
        html_selector.xpath("//title/text()").get()
        or html_selector.css("title::text").get()
        or meta_tags["og:title"]
        or meta_tags["og:site_name"]
        or meta_tags["pagename"]
    )
    return_obj["title"] = return_obj["title"].strip() if return_obj["title"] else None
    return_obj["language"] = (
        html_selector.xpath("//html/@lang").get()
        or html_selector.css("html::attr(lang)").get()
        or meta_tags["language"]
    )
    if return_obj["language"]:
        return_obj["language"] = return_obj["language"].split("-")[0].lower()
    return_obj["url"] = meta_tags["url"]
    return_obj["keywords"] = meta_tags["keywords"]
    return_obj["description"] = meta_tags["description"] or meta_tags["og:description"]
    return_obj["summary"] = meta_tags["summary"]
    return_obj["created_at"] = meta_tags["date"] or meta_tags["revised"]
    return_obj["changed"] = meta_tags["revised"]
    return_obj["thumbnail_url"] = meta_tags["og:image"]

    for k, v in return_obj.items():
        return_obj[k] = content.replace_whitespace(v)

    return_obj["content"] = extract_article_content(html_selector)

    return return_obj


def get_pdf_text(reader: PdfReader) -> tuple[str, list[tuple[str, PageObject]]]:
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


def get_pdf_meta(reader: PdfReader) -> dict:
    """
    Returns pdf metadata as a dict after its been cleaned.

    Args:
        reader: PdfReader from pypdf

    Returns:
        metadata object with possible keys: https://exiftool.org/TagNames/PDF.html
    """
    if not reader.metadata:
        return {}

    clean_metadata = {}
    for k, v in reader.metadata.items():
        resolved_value = v.get_object() if isinstance(v, IndirectObject) else v
        clean_metadata[str(k).removeprefix("/")] = parse_exif_date(resolved_value, apply_tz_offset=False)

    return clean_metadata


def parse_exif_date(value: Any, *, apply_tz_offset: bool) -> Any:
    """
    Parses a value as date if matched the conventional pdf/exif date format. If parsing fails,
    returns the original value

    Examples of str date format:
        "D:20150113143419Z00'00'"
        "D:20191018122555-04'00'"
        "D:20191018162538"

    Args:
        value: The value to parse.

    Returns:
        A datetime.datetime object if parsing is successful, otherwise the original value.
    """
    if not isinstance(value, str):
        return value

    if value.startswith("D:"):
        date_string = value.removeprefix("D:")

        proper_date_format = re.match(
            r"^(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?([+\-Z]{0,1})?(\d{2})?'?(\d{2})?'?$",
            date_string,
        )
        misformed_date_format = re.match(r"^[0-9zZ+\-']*$", date_string)

        if proper_date_format:
            year = int(proper_date_format.group(1))
            month = int(proper_date_format.group(2))
            day = int(proper_date_format.group(3))
            hour = int(proper_date_format.group(4)) if proper_date_format.group(4) else 0
            minute = int(proper_date_format.group(5)) if proper_date_format.group(5) else 0
            second = int(proper_date_format.group(6)) if proper_date_format.group(6) else 0
            tz_sign = proper_date_format.group(7) or "Z"
            tz_hour = int(proper_date_format.group(8)) if proper_date_format.group(8) else 0
            tz_minute = int(proper_date_format.group(9)) if proper_date_format.group(9) else 0

            # Handle timezone offset if matched
            if proper_date_format.group(7) and apply_tz_offset:
                tz_multiplier = -1 if tz_sign == "-" else 1
                offset = timedelta(hours=tz_hour, minutes=tz_minute) * tz_multiplier
                tz = timezone(offset=offset)
            else:
                tz = None

            try:
                return datetime(year, month, day, hour, minute, second, tzinfo=tz)
            except ValueError:
                log.debug("Failed to parse date string: %s", value)
                return None
        elif misformed_date_format:
            log.debug("Failed to parse date string: %s", value)
            return None
        else:
            pass  # Starts with D: but probably not a date

    return content.sanitize_text(value)


def get_pdf_links(pages: list[tuple[str, PageObject]]):
    """
    Returns a set of links for all pages in the PDF

    Args:
        pages: list of tuples containing (text, PageObject)

    Returns:
        (list[str]) unique set of links
    """
    key = "/Annots"
    uri = "/URI"
    ank = "/A"
    links = set()  # Use a set for unique links

    for page_item in pages:
        text, page = page_item
        # Get all visible links from text
        page_links = re.findall(r"https?://\S+|www\.\S+", text)
        for link in page_links:
            links.add(link)

        # Get all hidden links from annotations
        page_object = page.get_object()
        if key in page_object.keys():  # noqa: SIM118
            ann = page_object[key]
            for a in ann:
                u = a.get_object()
                try:
                    if ank in u and uri in u[ank].keys():  # noqa: SIM118
                        link = u[ank][uri]
                        # Convert bytes to string if necessary
                        if isinstance(link, bytes):
                            link = link.decode("utf-8")
                        links.add(link)
                except ValueError:
                    pass

    return list(links)
