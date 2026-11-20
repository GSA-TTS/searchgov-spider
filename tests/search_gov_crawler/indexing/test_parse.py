from datetime import UTC, datetime, timedelta, timezone
from io import BytesIO

import pytest
from freezegun import freeze_time
from pypdf import PdfReader
from scrapy import Selector

from search_gov_crawler.indexing.parse import (
    convert_html_scrapy,
    extract_article_content,
    get_html_meta,
    get_pdf_links,
    get_pdf_meta,
    get_pdf_text,
    parse_exif_date,
)


def test_convert_html_scrapy(test_scrapy_html_1):
    result = convert_html_scrapy(test_scrapy_html_1)

    assert isinstance(result, dict)
    assert "content" in result
    assert "title" in result
    assert result["content"] != ""
    assert "language" in result


def test_extract_article_content(test_scrapy_html_1):
    selector = Selector(text=test_scrapy_html_1)
    content = extract_article_content(selector)

    assert isinstance(content, str)
    assert len(content) > 0
    assert "<script>" not in content
    assert "<style>" not in content


def test_extract_article_content_no_body(monkeypatch, test_scrapy_html_1):
    monkeypatch.setattr(Selector, "css", lambda *_args, **_kwargs: None)
    selector = Selector(text=test_scrapy_html_1)
    assert extract_article_content(selector) == ""


def test_get_html_meta(test_scrapy_html_2):
    selector = Selector(text=test_scrapy_html_2)
    meta_values = get_html_meta(selector, ["description", "keywords", "og:title"])

    assert isinstance(meta_values, dict)
    assert "description" in meta_values
    assert "keywords" in meta_values
    assert "og:title" in meta_values


# ruff: disable[DTZ001]
PARSE_DATE_IF_VALID_TEST_CASES = [
    ("D:20230101023045", True, datetime(2023, 1, 1, 2, 30, 45)),
    ("D:20230101023045", False, datetime(2023, 1, 1, 2, 30, 45)),
    ("D:20191018122555-04'00'", True, datetime(2019, 10, 18, 12, 25, 55, tzinfo=timezone(offset=-timedelta(hours=4)))),
    ("D:20191018122555-04'00'", False, datetime(2019, 10, 18, 12, 25, 55)),
    ("D:20200405124512+10'00'", True, datetime(2020, 4, 5, 12, 45, 12, tzinfo=timezone(offset=timedelta(hours=10)))),
    ("D:20200405124512+10'00'", False, datetime(2020, 4, 5, 12, 45, 12)),
    (
        "D:20250930041000-02'30'",
        True,
        datetime(2025, 9, 30, 4, 10, 0, tzinfo=timezone(offset=-timedelta(hours=2, minutes=30))),
    ),
    ("D:20250930041000-02'30'", False, datetime(2025, 9, 30, 4, 10, 0)),
    (
        "D:19981223105959+05'30'",
        True,
        datetime(1998, 12, 23, 10, 59, 59, tzinfo=timezone(offset=timedelta(hours=5, minutes=30))),
    ),
    ("D:19981223105959+05'30'", False, datetime(1998, 12, 23, 10, 59, 59)),
    ("D:20150113143419Z00'00'", False, datetime(2015, 1, 13, 14, 34, 19)),
    (
        "D:20150113143419Z00'00'",
        True,
        datetime(2015, 1, 13, 14, 34, 19, tzinfo=timezone(offset=timedelta(hours=0, minutes=0))),
    ),
    ("D:invalid    ", False, "D:invalid"),
    ("Just a normal string", True, "Just a normal string"),
    ("D:20239901023045", False, None),
    ("D:/this/is/a/directory.pdf", False, "D:/this/is/a/directory.pdf"),
    ("D:00000000-0--000Z'0000'", False, None),
]
# ruff: enable[DTZ001]


@pytest.mark.parametrize(("input_val", "apply_tz_offset", "expected"), PARSE_DATE_IF_VALID_TEST_CASES)
def test_parse_exif_date_valid(input_val, apply_tz_offset, expected):
    """Test parse_exif_date with various valid values"""
    assert parse_exif_date(value=input_val, apply_tz_offset=apply_tz_offset) == expected


@pytest.mark.parametrize("input_val", ["D:20239901023045", "D:00000000-0--000"])
def test_parse_exif_date_datetime_debugging(caplog, input_val):
    with caplog.at_level("DEBUG"):
        parse_exif_date(value=input_val, apply_tz_offset=False)

        assert f"Failed to parse date string: {input_val}" in caplog.messages


def test_parse_exif_date_non_date():
    """Test parse_exif_date with a non-string value (or a string not starting with 'D:')."""
    non_date = "Not a date"
    result = parse_exif_date(value=non_date, apply_tz_offset=False)
    assert result == non_date.strip()


def test_parse_exif_date_non_string():
    non_string = 10
    assert parse_exif_date(value=non_string, apply_tz_offset=False) == non_string


@pytest.fixture
def multi_page_pdf_kwargs():
    return {
        "filename": "test_multi_page_pdf.pdf",
        "metadata": {"Title": "Test Multi Page PDF"},
        "pages": [
            {
                "text": (
                    "This is page 1 and wow there is a lot of cool stuff here! Visit https://example.com for more info."
                ),
                "links": ["https://hidden-link1.example.com"],
            },
            {
                "text": "But here on page 2 you wouldn't believe how interesting it is. Check out www.test.com and also https://example.com",
                "links": ["https://hidden-link2.example.com"],
            },
        ],
    }


@pytest.fixture
def multi_page_pdf_item(create_test_pdf_item, multi_page_pdf_kwargs):
    return create_test_pdf_item(**multi_page_pdf_kwargs)


def test_get_pdf_text(multi_page_pdf_item, multi_page_pdf_kwargs):
    """Test that get_pdf_text concatenates text from each page."""
    result, _ = get_pdf_text(PdfReader(BytesIO(multi_page_pdf_item.get("response_bytes"))))
    expected = " ".join([page["text"] for page in multi_page_pdf_kwargs["pages"]]) + " "
    assert result == expected


@pytest.fixture
@freeze_time(datetime(2026, 10, 31, 0, 0, 0, tzinfo=UTC))
def pdf_metadata(create_test_pdf_item):
    pdf_with_metadata = {
        "filename": "test_metadata_pdf.pdf",
        "metadata": {
            "Title": "Test Metadata PDF",
            "TestField": "Test Value",
            "IndirectCreationDate": datetime(2026, 10, 31, 0, 0, 0, tzinfo=UTC).astimezone().replace(tzinfo=None),
        },
        "pages": [{"text": "This is page 1 and wow there is a lot of cool stuff here!", "links": []}],
    }

    pdf_with_metadata = create_test_pdf_item(**pdf_with_metadata)
    return get_pdf_meta(PdfReader(BytesIO(pdf_with_metadata.get("response_bytes"))))


GET_PDF_META_TEST_CASES = [
    ("Title", "Test Metadata PDF"),
    ("CreationDate", datetime(2026, 10, 31, 0, 0, 0, tzinfo=UTC).astimezone().replace(tzinfo=None)),
    ("TestField", "Test Value"),
    ("IndirectCreationDate", datetime(2026, 10, 31, 0, 0, 0, tzinfo=UTC).astimezone().replace(tzinfo=None)),
]


@pytest.mark.parametrize(("metadata_field", "metadata_value"), GET_PDF_META_TEST_CASES)
def test_get_pdf_meta(pdf_metadata, metadata_field, metadata_value):
    """Test that metadata is cleaned and dates are parsed."""
    assert pdf_metadata[metadata_field] == metadata_value


def test_get_pdf_links(multi_page_pdf_item):
    _, pages = get_pdf_text(PdfReader(BytesIO(multi_page_pdf_item.get("response_bytes"))))
    links = get_pdf_links(pages)
    assert set(links) == {
        "https://example.com",
        "www.test.com",
        "https://hidden-link1.example.com",
        "https://hidden-link2.example.com",
    }
