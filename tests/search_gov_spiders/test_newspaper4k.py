from newspaper import Article
from pathlib import Path
from search_gov_crawler.search_engines.parse_html_scrapy import convert_html_scrapy


def load_file_with_pathlib(filename):
    script_dir = Path(__file__).resolve().parent
    file_path = script_dir / filename
    try:
        return file_path.read_text()
    except FileNotFoundError:
        return f"Error: File '{filename}' not found."

def test_newspaper4k_failed_html_parsing():
    """Test newspaper4k failed article text extraction from an HTML file."""
    html_content = load_file_with_pathlib("test_scrapy_html_1.html")
    article = Article(url="http://example.gov")
    article.download(input_html=html_content)
    article.parse()
    article.nlp()
    assert len(article.text) == 0

def test_convert_scrapy_successful_html_parsing():
    """Test convert_html_scrapy successful article text extraction from an HTML file."""
    html_content = load_file_with_pathlib("test_scrapy_html_1.html")
    result = convert_html_scrapy(html_content)
    assert isinstance(result, dict)
    assert "content" in result
    assert "title" in result
    assert result["content"] != ""
    assert "language" in result
   