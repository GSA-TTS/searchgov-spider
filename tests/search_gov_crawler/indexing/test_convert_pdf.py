import pytest
from pypdf.errors import PdfReadError

from search_gov_crawler.indexing import transform
from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem


@pytest.fixture
def convert_simple_pdf(create_test_pdf_item):
    """Test convert_pdf with a non-encrypted PDF simulation."""
    simple_pdf_kwargs = {
        "filename": "test_simple_pdf.pdf",
        "metadata": {"Title": "Test Simple PDF"},
        "pages": [{"text": "This is sample text written to validate PDF parsing.", "links": []}],
    }

    return transform.convert_pdf(create_test_pdf_item(**simple_pdf_kwargs))


CONVERT_SIMPLE_PDF_TEST_CASES = [
    ("title_en", "Test Simple PDF"),
    (
        "description_en",
        "Test Simple PDF test_simple_pdf.pdf This is sample text written to validate PDF parsing.",
    ),
    ("content_en", "Test Simple PDF test_simple_pdf.pdf This is sample text written to validate PDF parsing. "),
    ("id", "12ad0cb03901f73a72f257515736e19c60dc0e608fac895b0cf266273d2ed431"),
    ("basename", "test_simple_pdf"),
    ("extension", "pdf"),
    ("url_path", "/test_simple_pdf.pdf"),
    ("domain_name", "example.com"),
    ("dap_domain_visits_count", None),
]


@pytest.mark.parametrize(("field", "value"), CONVERT_SIMPLE_PDF_TEST_CASES)
def test_convert_pdf(convert_simple_pdf, field, value):
    assert convert_simple_pdf.get(field) == value


def test_convert_pdf_encrypted(create_test_pdf_item):
    """Test convert_pdf when the PDF is actually encrypted (should return None)."""
    encrpyted_pdf_kwargs = {
        "filename": "test_encrpyted_pdf.pdf",
        "metadata": {"Title": "Test Encrypted PDF"},
        "pages": [{"text": "This text is encrypted and you can't read it!", "links": []}],
        "encrpyted": True,
    }
    result = transform.convert_pdf(create_test_pdf_item(**encrpyted_pdf_kwargs))
    assert result == {}


@pytest.fixture
def sample_item():
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
