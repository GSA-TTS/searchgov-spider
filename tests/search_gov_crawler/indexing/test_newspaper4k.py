from newspaper import Article

from search_gov_crawler.indexing.parse import convert_html_scrapy


def test_newspaper4k_failed_html_parsing(test_scrapy_html_1):
    """Test newspaper4k failed article text extraction from an HTML file."""
    article = Article(url="http://example.gov")
    article.download(input_html=test_scrapy_html_1)
    article.parse()
    article.nlp()
    assert len(article.text) == 0


def test_convert_scrapy_successful_html_parsing(test_scrapy_html_1):
    """Test convert_html_scrapy successful article text extraction from an HTML file."""
    result = convert_html_scrapy(test_scrapy_html_1)
    assert isinstance(result, dict)
    assert "content" in result
    assert "title" in result
    assert result["content"] != ""
    assert "language" in result
