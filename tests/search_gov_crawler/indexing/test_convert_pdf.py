import pytest
from pypdf.errors import FileNotDecryptedError, PdfReadError

from search_gov_crawler.indexing import transform


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


def test_convert_pdf_normal(monkeypatch, fake_page, fake_pdf_reader):
    """Test convert_pdf with a non-encrypted PDF simulation."""
    fake_metadata = {"/Title": "Fake Title", "/CreationDate": "D:20230101000000"}
    pages = [fake_page("This is the content of the PDF.")]
    fake_reader = fake_pdf_reader(None, is_encrypted=False, pages=pages, metadata=fake_metadata)
    # Patch PdfReader so that any instantiation returns our fake_reader.
    monkeypatch.setattr(transform, "PdfReader", lambda _stream: fake_reader)

    response_bytes = b"dummy bytes representing pdf"
    url = "http://example.com/fake.pdf"
    result = transform.convert_pdf(response_bytes, url, response_language="en")

    # Check that the result is a dict with expected keys and values.
    assert result is not None
    # Since ALLOWED_LANGUAGE_CODE includes "en", we expect language suffix "_en" on these fields.
    assert result["title_en"] == "Fake Title"
    assert result["description_en"] == "Fake Title fake_basename.pdf Fake description"
    assert result["content_en"] == "Fake Title fake_basename.pdf This is the content of the PDF. "
    assert result["id"] == "dummy_sha"
    # Check values from dummy helpers.
    assert result["basename"] == "fake_basename"
    assert result["extension"] == "pdf"
    assert result["url_path"] == "/fake/path"
    assert result["domain_name"] == "fake.domain.com"
    assert result["dap_domain_visits_count"] is None


def test_convert_pdf_encrypted(monkeypatch, fake_pdf_reader):
    """Test convert_pdf when the PDF is actually encrypted (should return None)."""

    def raise_encrypted_error(*_args, **_kwargs):
        msg = "PDF is encrypted and cannot be read."
        raise FileNotDecryptedError(msg)

    fake_reader = fake_pdf_reader(None, is_encrypted=True)
    monkeypatch.setattr(transform, "PdfReader", lambda _stream: fake_reader)
    monkeypatch.setattr(transform, "get_pdf_meta", raise_encrypted_error)
    response_bytes = b"dummy bytes representing pdf"
    url = "http://example.com/encrypted.pdf"
    result = transform.convert_pdf(response_bytes, url)
    assert result is None


def test_convert_pdf_stream_error(caplog, mocker):
    mock_reader = mocker.patch("pypdf.PdfReader.__init__")
    error_msg = "Error reading PDF"
    mock_reader.side_effect = PdfReadError(error_msg)
    response_bytes = b"some bytes representing pdf"
    url = "http://example.com/bad-read-pdf.pdf"
    with caplog.at_level("WARNING"):
        doc = transform.convert_pdf(response_bytes, url)

    assert f"Could not download PDF file at {url}: {error_msg}" in caplog.messages
    assert doc is None


def test_add_title_and_filename():
    """Test that add_title_and_filename correctly formats the content."""
    kwargs = {"original_value": "This is some sample content", "title": "Sample PDF", "filename": "sample.pdf"}
    output = transform.add_title_and_filename(**kwargs)
    assert output == "Sample PDF sample.pdf This is some sample content"
