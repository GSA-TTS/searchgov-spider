import json
import re
from pathlib import Path
from typing import Any, Optional

from scrapy.linkextractors import LinkExtractor

# fmt: off
FILTER_EXTENSIONS = [
    # archives
    "7z", "7zip", "bz2", "rar", "tar", "tar.gz", "xz", "zip", "gz",
    # images
    "mng", "pct", "bmp", "gif", "jpg", "jpeg", "png", "pst", "psp", "image",
    "tif", "tiff", "ai", "drw", "dxf", "eps", "ps", "svg", "cdr", "ico",
    # audio
    "mp3", "wma", "ogg", "wav", "ra", "aac", "mid", "au", "aiff", "media",
    # video
    "3gp", "asf", "asx", "avi", "mov", "mp4", "mpg", "qt", "rm", "swf",
    "wmv", "m4a", "m4v", "flv", "webm",
    # office suites
    "ppt", "pptx", "pps", "odt", "ods", "odg", "odp",
    # other
    "css", "exe", "bin", "rss", "dmg", "iso", "apk", "js", "xml", "ibooks",
    "ics", "nc", "nc4", "prj", "sfx", "eventsource", "fetch", "stylesheet",
    "websocket", "xhr", "font", "manifest", "hdf", "geojson",
]
# fmt: on

ALLOWED_CONTENT_TYPE = [
    "text/html",
    "text/plain",
    "application/msword",
    "application/pdf",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]


ES_ALLOWED_CONTENT_TYPE = [
    "text/html",
]

ALLOWED_CONTENT_TYPE_OUTPUT_MAP = {
    "csv": ALLOWED_CONTENT_TYPE,
    "endpoint": ALLOWED_CONTENT_TYPE,
    "elasticsearch": ES_ALLOWED_CONTENT_TYPE,
}

LINK_DENY_REGEX_STR = ["calendar", "location-contact", "DTMO-Site-Map/FileId/"]

domain_spider_link_extractor = LinkExtractor(
    allow=(),
    deny=LINK_DENY_REGEX_STR,
    deny_extensions=FILTER_EXTENSIONS,
    tags=("a", "area", "va-link"),  # specified to account for custom link tags
    unique=True,
)


def split_allowed_domains(allowed_domains: str) -> list[str]:
    """Remove path information from comma-seperated list of domains"""
    host_only_domains = []

    all_domains = allowed_domains.split(",")
    for domain in all_domains:
        if (slash_idx := domain.find("/")) > 0:
            host_only_domains.append(domain[:slash_idx])
        else:
            host_only_domains.append(domain)

    return host_only_domains


def is_valid_content_type(content_type_header: Any, output_target: str) -> bool:
    """Check that content type header is in list of allowed values"""
    content_type_header = str(content_type_header)
    for type_regex in ALLOWED_CONTENT_TYPE_OUTPUT_MAP[output_target]:
        if re.search(type_regex, content_type_header):
            return True
    return False


def get_crawl_sites(crawl_file_path: Optional[str] = None) -> list[dict]:
    """Read in list of crawl sites from json file"""
    if not crawl_file_path:
        crawl_file = Path(__file__).parent.parent.parent / "domains" / "crawl-sites-production.json"
    else:
        crawl_file = Path(crawl_file_path)

    return json.loads(crawl_file.resolve().read_text(encoding="utf-8"))


def default_starting_urls(handle_javascript: bool) -> list[str]:
    """Created default list of starting urls filtered by ability to handle javascript"""

    crawl_sites_records = get_crawl_sites()
    return [
        record["starting_urls"] for record in crawl_sites_records if record["handle_javascript"] is handle_javascript
    ]


def default_allowed_domains(handle_javascript: bool, remove_paths: bool = True) -> list[str]:
    """Created default list of domains filtered by ability to handle javascript"""

    allowed_domains = []

    crawl_sites_records = get_crawl_sites()
    for record in crawl_sites_records:
        if record["handle_javascript"] is handle_javascript:
            domains = record["allowed_domains"]
            if remove_paths:
                allowed_domains.extend(split_allowed_domains(domains))
            else:
                allowed_domains.extend(domains.split(","))

    return allowed_domains


def validate_spider_arguments(allowed_domains: str | None, start_urls: str | None, output_target: str) -> None:
    """Common logic used to validate spider arguements and raise errors"""

    if any([allowed_domains, start_urls]) and not all([allowed_domains, start_urls]):
        msg = "Invalid arguments: allowed_domains and start_urls must be used together or not at all."
        raise ValueError(msg)

    if output_target not in ALLOWED_CONTENT_TYPE_OUTPUT_MAP:
        msg = (
            "Invalid arguments: output_target must be one of the following: "
            f"{list(ALLOWED_CONTENT_TYPE_OUTPUT_MAP.keys())}"
        )
        raise ValueError(msg)
