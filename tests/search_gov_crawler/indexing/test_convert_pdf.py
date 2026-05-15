import pytest
from pypdf.errors import FileNotDecryptedError, PdfReadError

from search_gov_crawler.indexing import transform
from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem


@pytest.fixture(autouse=True)
def patch_helpers(monkeypatch):
    def mock_get_base_extension(*_args, **_kwargs):
        return ("fake_basename", "pdf", "fake_basename.pdf")

    def mock_summarize_text(*_args, **_kwargs):
        # Return a tuple: (description, list of keywords)
        return ("Fake description", ["keyword1", "keyword2"])

    def mock_generate_url_sha256(*_args, **_kwargs):
        return "dummy_sha"

    def mock_current_utc_iso():
        return "2023-01-01T00:00:00Z"

    def mock_parse_dates_safely(*date_str):
        # For testing, simply return the date_str (or a default if none provided)
        return date_str or "parse_date_safely"

    def mock_get_url_path(*_args, **_kwargs):
        return "/fake/path"

    def mock_get_domain_name(*_args, **_kwargs):
        return "fake.domain.com"

    def mock_sanitize_text(text):
        return text.strip()

    monkeypatch.setattr("search_gov_crawler.indexing.transform.helpers.get_base_extension", mock_get_base_extension)
    monkeypatch.setattr("search_gov_crawler.indexing.transform.helpers.summarize_text", mock_summarize_text)
    monkeypatch.setattr("search_gov_crawler.indexing.transform.helpers.generate_url_sha256", mock_generate_url_sha256)
    monkeypatch.setattr("search_gov_crawler.indexing.transform.helpers.current_utc_iso", mock_current_utc_iso)
    monkeypatch.setattr("search_gov_crawler.indexing.transform.helpers.parse_dates_safely", mock_parse_dates_safely)
    monkeypatch.setattr("search_gov_crawler.indexing.transform.helpers.get_url_path", mock_get_url_path)
    monkeypatch.setattr("search_gov_crawler.indexing.transform.helpers.get_domain_name", mock_get_domain_name)
    monkeypatch.setattr("search_gov_crawler.indexing.transform.content.sanitize_text", mock_sanitize_text)
    # Ensure the allowed language list includes "en" so that we get a valid language suffix.
    monkeypatch.setattr("search_gov_crawler.indexing.transform.helpers.ALLOWED_LANGUAGE_CODE", {"en": "english"})


@pytest.fixture(name="sample_item")
def fixture_sample_item():
    return SearchGovSpidersItem(
        crawl_depth=5,
        creator="test",
        download_milliseconds=100,
        source_url="http://example.com/fake-page",
        response_bytes=b"yadda yadda yadda",
        url="http://example.com/fake.pdf",
        response_language="en",
        output_target="opensearch",
    )


@pytest.fixture(name="convert_pdf_normal")
def fixture_convert_pdf_normal(monkeypatch, fake_page, fake_pdf_reader, sample_item):
    """Test convert_pdf with a non-encrypted PDF simulation."""
    fake_metadata = {"/Title": "Fake Title", "/CreationDate": "D:20230101000000"}
    pages = [fake_page("This is the content of the PDF.")]
    fake_reader = fake_pdf_reader(None, is_encrypted=False, pages=pages, metadata=fake_metadata)
    # Patch PdfReader so that any instantiation returns our fake_reader.
    monkeypatch.setattr(transform, "PdfReader", lambda _stream: fake_reader)
    return transform.convert_pdf(item=sample_item)


CONVERT_PDF_TEST_CASES = [
    ("title_en", "Fake Title"),
    ("description_en", "Fake Title fake_basename.pdf Fake description"),
    ("content_en", "Fake Title fake_basename.pdf This is the content of the PDF. "),
    ("id", "dummy_sha"),
    ("basename", "fake_basename"),
    ("extension", "pdf"),
    ("url_path", "/fake/path"),
    ("domain_name", "fake.domain.com"),
    ("dap_domain_visits_count", None),
]


@pytest.mark.parametrize(("field", "value"), CONVERT_PDF_TEST_CASES)
def test_convert_pdf(convert_pdf_normal, field, value):
    assert convert_pdf_normal.get(field) == value


def test_convert_pdf_encrypted(monkeypatch, fake_pdf_reader, sample_item):
    """Test convert_pdf when the PDF is actually encrypted (should return None)."""

    def raise_encrypted_error(*_args, **_kwargs):
        msg = "PDF is encrypted and cannot be read."
        raise FileNotDecryptedError(msg)

    fake_reader = fake_pdf_reader(None, is_encrypted=True)
    monkeypatch.setattr(transform, "PdfReader", lambda _stream: fake_reader)
    monkeypatch.setattr(transform, "get_pdf_meta", raise_encrypted_error)

    result = transform.convert_pdf(item=sample_item)
    assert result == {}


def test_convert_pdf_stream_error(caplog, mocker, sample_item):
    mock_reader = mocker.patch("pypdf.PdfReader.__init__")
    error_msg = "Error reading PDF"
    mock_reader.side_effect = PdfReadError(error_msg)
    with caplog.at_level("WARNING"):
        doc = transform.convert_pdf(item=sample_item)

    assert f"Could not download PDF file for item {sample_item}: {error_msg}" in caplog.messages
    assert doc == {}


def test_add_title_and_filename():
    """Test that add_title_and_filename correctly formats the content."""
    kwargs = {"original_value": "This is some sample content", "title": "Sample PDF", "filename": "sample.pdf"}
    output = transform.add_title_and_filename(**kwargs)
    assert output == "Sample PDF sample.pdf This is some sample content"
