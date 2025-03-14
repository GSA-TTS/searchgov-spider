from search_gov_crawler.elasticsearch import convert_html_i14y
from search_gov_crawler.search_gov_spiders.helpers import content

def test_convert_html_valid_article():
    html_content = """
    <html lang="en">
    <head>
        <title>Test Article Title</title>
        <meta name="description" content="Test article description.">
        <meta name="keywords" content="test, article, keywords">
        <meta property="og:image" content="https://example.com/image.jpg">
        <meta name="language" content="en">
    </head>
    <body>
        <h1>Test Article Title</h1>
        <p>This is the main content of the test article.</p>
    </body>
    </html>
    """
    response_bytes = html_content.encode()
    url = "https://example.com/test-article"
    result = convert_html_i14y.convert_html(response_bytes, url, "en")

    assert result is not None
    assert result["title_en"] == "Test Article Title"
    assert result["description_en"] == "Test article description."
    assert "This is the main content of the test article." in result["content_en"]
    assert result["thumbnail_url"] == "https://example.com/image.jpg"
    assert result["language"] == "en"
    assert result["path"] == url
    assert result["basename"] == "test-article"
    assert result["extension"] == None
    assert result["domain_name"] == "example.com"
    assert result["url_path"] == "/test-article"
    assert len(result["_id"]) == 64  # SHA256 hash

def test_convert_html_no_content():
    html_content = """
    <html lang="en">
    <head>
        <title>Test Article Title</title>
    </head>
    <body>
    </body>
    </html>
    """
    url = "https://example.com/test-article"
    result = convert_html_i14y.convert_html(html_content.encode(), url, "en")
    assert result is None

def test_convert_html_no_title_or_description():
    html_content = """
    <html lang="en">
    <head>
    </head>
    <body>
        <p>This is the main content of the test article.</p>
    </body>
    </html>
    """
    url = "https://example.com/test-article"
    result = convert_html_i14y.convert_html(html_content.encode(), url, "en")
    content = "This is the main content of the test article."
    assert result is not None
    assert result["title_en"] is None
    assert result["description_en"] in content
    assert "This is the main content of the test article." in result["content_en"]

def test_convert_html_with_meta_site_name():
    html_content = """
    <html lang="en">
    <head>
        <meta property="og:site_name" content="Example Site">
    </head>
    <body>
        <h1>Test Article Title</h1>
        <p>This is the main content.</p>
    </body>
    </html>
    """
    url = "https://example.com/test-article"
    result = convert_html_i14y.convert_html(html_content.encode(), url, "en")
    assert result is not None
    assert result["title_en"] == "Example Site"  # Uses meta_site_name
    assert "This is the main content." in result["content_en"]

def test_convert_html_with_publish_date():
    html_content = """
    <html lang="en">
    <head>
        <meta name="date" content="2024-03-15">
    </head>
    <body>
        <h1>Test Article Title</h1>
        <p>This is the main content.</p>
    </body>
    </html>
    """
    url = "https://example.com/test-article"
    result = convert_html_i14y.convert_html(html_content.encode(), url, "en")
    assert result is not None
    assert result["updated"] is not None # newspaper4k may or may not parse date from meta; this checks for any value.

def test_convert_html_with_out_publish_date():
    html_content = """
    <html lang="en">
    <head>
        <meta name="date">
    </head>
    <body>
        <h1>Test Article Title</h1>
        <p>This is the main content.</p>
    </body>
    </html>
    """
    url = "https://example.com/test-article"
    result = convert_html_i14y.convert_html(html_content.encode(), url, "en")
    assert result is not None
    assert result["updated"] is not ""
    assert result["updated"] is None # newspaper4k may or may not parse date from meta; this checks for any value.

def test_convert_html_languages():
    html_content = """
        <html>
            <head>
                <title>Some Title</title>
                <meta name="description" content="这是一个测试描述">
                <meta name="language" content="zh">
            </head>
            <body>
                <div>
                    <p>
                        労化合測断秒化任面件気子人球分向無圧。了作果批入選教済球主運私信成笑論情禁。首着場研打表阪東日善能最囲値名陣必。想必愛交備見事新演内高青録断狙。詳期斉幕善確込対危継属会提円和動会分子。中常特処秘局創企真刊葉戸獲人師。前場明持二本聞通調写何観。薫大本設紋証済球取縮不園。辺案惑報湖買含応給奥専申琴真集情月続。
                    </p>
                </div>
            </body>
        </html>
    """
    url = "https://example.cn/article"
    
    result = convert_html_i14y.convert_html(html_content.encode(), url, "zh")

    assert result is not None
    assert result["content_zh"] == "労化合測断秒化任面件気子人球分向無圧。了作果批入選教済球主運私信成笑論情禁。首着場研打表阪東日善能最囲値名陣必。想必愛交備見事新演内高青録断狙。詳期斉幕善確込対危継属会提円和動会分子。中常特処秘局創企真刊葉戸獲人師。前場明持二本聞通調写何観。薫大本設紋証済球取縮不園。辺案惑報湖買含応給奥専申琴真集情月続。"
    assert result["title_zh"] == "Some Title"
    assert result["description_zh"] == content.sanitize_text("这是一个测试描述")
