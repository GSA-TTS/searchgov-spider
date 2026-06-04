from pathlib import Path

import pytest


@pytest.fixture(name="test_scrapy_html_1")
def fixture_test_scrapy_html_1():
    return Path(Path(__file__).resolve().parent / "test_scrapy_html_1.html").read_text()


@pytest.fixture(name="test_scrapy_html_2")
def fixture_test_scrapy_html_2():
    return Path(Path(__file__).resolve().parent / "test_scrapy_html_2.html").read_text()
