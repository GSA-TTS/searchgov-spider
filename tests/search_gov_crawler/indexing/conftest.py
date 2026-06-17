from pathlib import Path

import pytest


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


class FakePdfReader:
    def __init__(self, _stream, is_encrypted, pages=None, metadata=None):
        self.is_encrypted = is_encrypted or False
        self.pages = pages if pages is not None else []
        self.metadata = metadata if metadata is not None else {}


@pytest.fixture(name="fake_page")
def fixture_fake_page():
    def _fake_page(text):
        return FakePage(text)

    return _fake_page


@pytest.fixture(name="fake_pdf_reader")
def fixture_fake_pdf_reader():
    def _fake_pdf_readeer(*args, **kwargs):
        return FakePdfReader(*args, **kwargs)

    return _fake_pdf_readeer
