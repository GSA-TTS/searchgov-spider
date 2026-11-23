from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem


@pytest.fixture(name="test_scrapy_html_1")
def fixture_test_scrapy_html_1():
    return Path(Path(__file__).resolve().parent / "test_scrapy_html_1.html").read_text()


@pytest.fixture(name="test_scrapy_html_2")
def fixture_test_scrapy_html_2():
    return Path(Path(__file__).resolve().parent / "test_scrapy_html_2.html").read_text()


@pytest.fixture(scope="session")
def temp_pdf_dir(tmp_path_factory):
    return Path(tmp_path_factory.mktemp("pdf_testing"))


@pytest.fixture
def create_test_pdf(temp_pdf_dir):  # noqa: C901
    def _write_page(canvas: canvas.Canvas, page: dict) -> canvas.Canvas:
        text_obj = canvas.beginText(100, 750)
        text_obj.setFont("Helvetica", 12)

        text_obj.textOut(page["text"])
        canvas.drawText(text_obj)
        for idx, link in enumerate(page["links"], start=1):
            canvas.linkURL(link, rect=(0, 0 + idx, *letter))
        canvas.showPage()

        return canvas

    def _pdf_generator(
        filename: str,
        pages: list[dict],
        metadata: dict,
        encrpyted: bool = False,  # noqa: FBT001,FBT002
        scrub_metadata: bool = False,  # noqa: FBT001,FBT002
    ) -> tuple[Path, bytes]:
        pdf_path = temp_pdf_dir / filename
        canvas_kwargs = {
            "filename": str(pdf_path),
            "encrypt": "user_password123" if encrpyted else None,
        }
        c = canvas.Canvas(**canvas_kwargs, pagesize=letter)

        built_in_metadata_fields = {
            "Title": c.setTitle,
            "Author": c.setAuthor,
            "Subject": c.setSubject,
            "Keywords": c.setKeywords,
            "Creator": c.setCreator,
        }
        for field_name, setter in built_in_metadata_fields.items():
            field = metadata.pop(field_name, None)
            if field:
                setter(field)

        for page in pages:
            _write_page(canvas=c, page=page)

        c.save()

        if metadata or scrub_metadata:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            existing_metadata = reader.metadata
            if scrub_metadata:
                writer.metadata = None
            else:
                if existing_metadata:
                    writer.add_metadata(existing_metadata)

                new_metadata = {}
                for k, v in metadata.items():
                    new_metadata_key = f"/{k}" if not k.startswith("/") else k
                    if new_metadata_key.startswith("/Indirect"):
                        raw_indirect = reader.metadata.raw_get(new_metadata_key.replace("Indirect", ""))
                        resolved_value = raw_indirect.get_object()
                        new_metadata_value = resolved_value
                    else:
                        new_metadata_value = v

                    new_metadata[new_metadata_key] = new_metadata_value

                writer.add_metadata(new_metadata)

            writer.write(pdf_path)
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
