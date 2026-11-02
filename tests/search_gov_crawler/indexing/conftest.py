from pathlib import Path

import pytest
from reportlab.pdfbase.pdfdoc import PDFString
from reportlab.pdfgen import canvas

from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem


@pytest.fixture(name="test_scrapy_html_1")
def fixture_test_scrapy_html_1():
    return Path(Path(__file__).resolve().parent / "test_scrapy_html_1.html").read_text()


@pytest.fixture(name="test_scrapy_html_2")
def fixture_test_scrapy_html_2():
    return Path(Path(__file__).resolve().parent / "test_scrapy_html_2.html").read_text()


class FakePage:
    def __init__(self, text):
        self._text = text
        self._object = {}

    def extract_text(self):
        return self._text

    def get_object(self):
        return self._object


@pytest.fixture(name="fake_page")
def fixture_fake_page():
    def _fake_page(text):
        return FakePage(text)

    return _fake_page


@pytest.fixture(scope="session")
def temp_pdf_dir(tmp_path_factory):
    return Path(tmp_path_factory.mktemp("pdf_testing"))


@pytest.fixture
def create_test_pdf(temp_pdf_dir):
    def _write_page(canvas: canvas.Canvas, text: str) -> canvas.Canvas:
        text_obj = canvas.beginText(100, 750)
        text_obj.setFont("Helvetica", 12)

        text_obj.textOut(text)
        canvas.drawText(text_obj)
        canvas.showPage()

        return canvas

    def _pdf_generator(
        filename: str,
        page_text: list[str],
        metadata: dict,
        encrpyted: bool = False,  # noqa: FBT001,FBT002
    ) -> tuple[Path, bytes]:
        pdf_path = temp_pdf_dir / filename
        canvas_kwargs = {
            "filename": str(pdf_path),
            "encrypt": "user_password123" if encrpyted else None,
        }
        c = canvas.Canvas(**canvas_kwargs)

        for k, v in metadata.items():
            if str(k).lower() == "title":
                c.setTitle(v)
            else:
                c._doc.info.__dict__[k] = PDFString(v)

        for page in page_text:
            _write_page(canvas=c, text=page)

        c.save()
        return pdf_path, pdf_path.read_bytes()

    return _pdf_generator


@pytest.fixture
def create_test_pdf_item(create_test_pdf):
    def _create_test_pdf_item(*args, **kwargs):
        pdf_path, pdf_bytes = create_test_pdf(*args, **kwargs)
        return SearchGovSpidersItem(
            crawl_depth=5,
            creator="test",
            download_milliseconds=100,
            source_url="http://example.com/fake-page",
            response_bytes=pdf_bytes,
            url=f"http://example.com/{pdf_path.name}",
            response_language="en",
            output_target="opensearch",
        )

    return _create_test_pdf_item
