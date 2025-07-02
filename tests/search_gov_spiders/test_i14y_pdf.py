from datetime import datetime, timedelta, timezone

import pytest
from pypdf.generic import IndirectObject

from search_gov_crawler.elasticsearch import convert_pdf_i14y


class FakePage:
    def __init__(self, text):
        self._text = text
        self._object = {}

    def extract_text(self):
        return self._text

    def get_object(self):
        return self._object


class FakePdfReader:
    def __init__(self, stream, is_encrypted=False, pages=None, metadata=None):
        self.is_encrypted = is_encrypted
        self.pages = pages if pages is not None else []
        self.metadata = metadata if metadata is not None else {}


# Dummy helper functions to override external dependencies. We're already testing them in other places
def dummy_get_base_extension(url):
    return ("fake_basename", "pdf")


def dummy_separate_file_name(filename):
    return "Fake Title from filename"


def dummy_summarize_text(text, url, lang_code):
    # Return a tuple: (description, list of keywords)
    return ("Fake description", ["keyword1", "keyword2"])


def dummy_generate_url_sha256(url):
    return "dummy_sha"


def dummy_detect_lang(text):
    return "en"


def dummy_current_utc_iso():
    return "2023-01-01T00:00:00Z"


def dummy_parse_date_safely(date_str):
    # For testing, simply return the date_str (or a default if none provided)
    return date_str if date_str else "parse_date_safely"


def dummy_get_url_path(url):
    return "/fake/path"


def dummy_get_domain_name(url):
    return "fake.domain.com"


def dummy_sanitize_text(text):
    return text.strip()


# ----- Pytest fixture to patch helper functions -----


@pytest.fixture(autouse=True)
def patch_helpers(monkeypatch):
    monkeypatch.setattr(convert_pdf_i14y, "get_base_extension", dummy_get_base_extension)
    monkeypatch.setattr(convert_pdf_i14y, "separate_file_name", dummy_separate_file_name)
    monkeypatch.setattr(convert_pdf_i14y, "summarize_text", dummy_summarize_text)
    monkeypatch.setattr(convert_pdf_i14y, "generate_url_sha256", dummy_generate_url_sha256)
    monkeypatch.setattr(convert_pdf_i14y, "detect_lang", dummy_detect_lang)
    monkeypatch.setattr(convert_pdf_i14y, "current_utc_iso", dummy_current_utc_iso)
    monkeypatch.setattr(convert_pdf_i14y, "parse_date_safely", dummy_parse_date_safely)
    monkeypatch.setattr(convert_pdf_i14y, "get_url_path", dummy_get_url_path)
    monkeypatch.setattr(convert_pdf_i14y, "get_domain_name", dummy_get_domain_name)
    monkeypatch.setattr(convert_pdf_i14y.content, "sanitize_text", dummy_sanitize_text)
    # Ensure the allowed language list includes "en" so that we get a valid language suffix.
    monkeypatch.setattr(convert_pdf_i14y, "ALLOWED_LANGUAGE_CODE", {"en": "english"})


# ----- Tests for helper functions -----


def test_get_pdf_text():
    """Test that get_pdf_text concatenates text from each page."""
    fake_page_content_1 = """
    Lorem Ipsum is simply dummy text of the printing and typesetting industry.
    Lorem Ipsum has been the industry's standard dummy text ever since the 1500s,
    when an unknown printer took a galley of type and scrambled it to make a type specimen book.
    It has survived not only five centuries, but also the leap into electronic typesetting, remaining essentially unchanged.
    """
    fake_page_content_2 = f"Page 2 content: {fake_page_content_1}"
    pages = [FakePage(fake_page_content_1), FakePage(fake_page_content_2)]
    fake_reader = FakePdfReader(None, pages=pages)
    result, _ = convert_pdf_i14y.get_pdf_text(fake_reader)
    expected = f"{fake_page_content_1} {fake_page_content_2} "
    assert result == expected


GET_PDF_META_TEST_CASES = [
    (None, {}),
    (
        {"/Title": "Fake Title", "/CreationDate": "D:20230101000000"},
        {"Title": "Fake Title", "CreationDate": datetime(2023, 1, 1, 0, 0, 0)},
    ),
    (
        {"Test Field": "Test Value", "/CreationDate": "D:20230101000000"},
        {"Test Field": "Test Value", "CreationDate": datetime(2023, 1, 1, 0, 0, 0)},
    ),
    (
        {"/IndirectField": IndirectObject(idnum=0, generation=0, pdf="Resolved Value")},
        {"IndirectField": "Resolved Value"},
    ),
]


@pytest.mark.parametrize(("metadata", "expected_output"), GET_PDF_META_TEST_CASES)
def test_get_pdf_meta(monkeypatch, metadata, expected_output):
    """Test that metadata is cleaned and dates are parsed."""
    monkeypatch.setattr(IndirectObject, "get_object", lambda x: x.pdf)
    fake_reader = FakePdfReader(None, metadata=metadata)
    assert convert_pdf_i14y.get_pdf_meta(fake_reader) == expected_output


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
    ("D:invalid    ", False, "D:invalid"),
    ("Just a normal string", True, "Just a normal string"),
]


@pytest.mark.parametrize(("input_val", "apply_tz_offset", "expected"), PARSE_DATE_IF_VALID_TEST_CASES)
def test_parse_if_date_valid(input_val, apply_tz_offset, expected):
    """Test parse_if_date with various valid values"""
    assert convert_pdf_i14y.parse_if_date(input_val, apply_tz_offset) == expected


def test_parse_if_date_non_date():
    """Test parse_if_date with a non-string value (or a string not starting with 'D:')."""
    non_date = "Not a date"
    result = convert_pdf_i14y.parse_if_date(non_date)
    assert result == non_date.strip()


# ----- Tests for the main conversion function -----


def test_convert_pdf_normal(monkeypatch):
    """Test convert_pdf with a non-encrypted PDF simulation."""
    fake_metadata = {"/Title": "Fake Title", "/CreationDate": "D:20230101000000"}
    pages = [FakePage("This is the content of the PDF.")]
    fake_reader = FakePdfReader(None, is_encrypted=False, pages=pages, metadata=fake_metadata)
    # Patch PdfReader so that any instantiation returns our fake_reader.
    monkeypatch.setattr(convert_pdf_i14y, "PdfReader", lambda stream: fake_reader)

    response_bytes = b"dummy bytes representing pdf"
    url = "http://example.com/fake.pdf"
    result = convert_pdf_i14y.convert_pdf(response_bytes, url, response_language="en")

    # Check that the result is a dict with expected keys and values.
    assert result is not None
    # Since ALLOWED_LANGUAGE_CODE includes "en", we expect language suffix "_en" on these fields.
    assert result["title_en"] == "Fake Title"
    assert result["description_en"] == "Fake Title fake_basename.pdf Fake description"
    assert result["content_en"] == "Fake Title fake_basename.pdf This is the content of the PDF. "
    assert result["_id"] == "dummy_sha"
    # Check values from dummy helpers.
    assert result["basename"] == "fake_basename"
    assert result["extension"] == "pdf"
    assert result["url_path"] == "/fake/path"
    assert result["domain_name"] == "fake.domain.com"


def test_convert_pdf_encrypted(monkeypatch):
    """Test convert_pdf when the PDF is encrypted (should return None)."""
    fake_reader = FakePdfReader(None, is_encrypted=True)
    monkeypatch.setattr(convert_pdf_i14y, "PdfReader", lambda stream: fake_reader)
    response_bytes = b"dummy bytes representing pdf"
    url = "http://example.com/encrypted.pdf"
    result = convert_pdf_i14y.convert_pdf(response_bytes, url)
    assert result is None


def test_add_title_and_filename():
    """Test that add_title_and_filename correctly formats the content."""
    doc = {
        "title_en": "Sample PDF",
        "basename": "sample",
        "extension": "pdf",
        "content_en": "This is some sample content.",
    }
    convert_pdf_i14y.add_title_and_filename("content_en", "title_en", doc)
    expected_content = "Sample PDF sample.pdf This is some sample content."
    assert doc["content_en"] == expected_content


def test_get_links_set(mocker):
    """Test that get_links_set extracts unique links from PDF pages."""

    page1_text = "Visit https://example.com for more info."
    page2_text = "Check out www.test.com and also https://example.com"

    fake_page1 = mocker.MagicMock()
    fake_page1.get_object.return_value = {}

    fake_page2 = mocker.MagicMock()
    fake_page2.get_object.return_value = {}

    page_items = [(page1_text, fake_page1), (page2_text, fake_page2)]

    links = convert_pdf_i14y.get_links_set(page_items)

    expected_links = {"https://example.com", "www.test.com"}

    assert set(links) == expected_links
