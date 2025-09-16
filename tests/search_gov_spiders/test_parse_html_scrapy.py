from scrapy import Selector
from pathlib import Path
from search_gov_crawler.search_engines.parse_html_scrapy import convert_html_scrapy, extract_article_content, get_meta_values

def load_file_with_pathlib(filename):
    script_dir = Path(__file__).resolve().parent
    file_path = script_dir / filename
    try:
        return file_path.read_text()
    except FileNotFoundError:
        return f"Error: File '{filename}' not found."

def test_convert_html_scrapy():
    html_content = load_file_with_pathlib("test_scrapy_html_1.html")
    result = convert_html_scrapy(html_content)
    
    assert isinstance(result, dict)
    assert "content" in result
    assert "title" in result
    assert result["content"] != ""
    assert "language" in result

def test_extract_article_content():
    html_content = load_file_with_pathlib("test_scrapy_html_1.html")
    selector = Selector(text=html_content)
    content = extract_article_content(selector)
    
    assert isinstance(content, str)
    assert len(content) > 0
    assert "<script>" not in content
    assert "<style>" not in content

def test_get_meta_values():
    html_content = load_file_with_pathlib("test_scrapy_html_2.html")
    selector = Selector(text=html_content)
    meta_values = get_meta_values(selector, ["description", "keywords", "og:title"])
    
    assert isinstance(meta_values, dict)
    assert "description" in meta_values
    assert "keywords" in meta_values
    assert "og:title" in meta_values
