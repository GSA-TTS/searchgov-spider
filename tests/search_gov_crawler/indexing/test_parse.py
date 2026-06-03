from scrapy import Selector

from search_gov_crawler.indexing.parse import convert_html_scrapy, extract_article_content, get_meta_values


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


def test_get_meta_values(test_scrapy_html_2):
    selector = Selector(text=test_scrapy_html_2)
    meta_values = get_meta_values(selector, ["description", "keywords", "og:title"])

    assert isinstance(meta_values, dict)
    assert "description" in meta_values
    assert "keywords" in meta_values
    assert "og:title" in meta_values
