import pytest

from search_gov_crawler.indexing import transform
from search_gov_crawler.search_gov_spiders.helpers import content
from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem


@pytest.fixture(name="create_item_with_content")
def fixture_create_item_with_content():
    def _create_item_with_content(content: str, url: str = "https://example.com/test-article", lang: str = "en"):
        return SearchGovSpidersItem(
            response_bytes=content.encode(),
            crawl_depth=2,
            creator="test",
            content_type="text/html",
            download_milliseconds=100,
            output_target="opensearch",
            response_language=lang,
            source_url="test",
            url=url,
        )

    return _create_item_with_content


def test_convert_html_valid_article(create_item_with_content):
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
    item = create_item_with_content(content=html_content)
    result = transform.convert_html(item=item)

    assert result is not None
    assert result["title_en"] == "Test Article Title"
    assert result["description_en"] == "Test article description."
    assert "This is the main content of the test article." in result["content_en"]
    assert result["thumbnail_url"] == "https://example.com/image.jpg"
    assert result["language"] == "en"
    assert result["path"] == "https://example.com/test-article"
    assert result["basename"] == "test-article"
    assert result["extension"] is None
    assert result["domain_name"] == "example.com"
    assert result["url_path"] == "/test-article"
    assert len(result["id"]) == 64  # SHA256 hash
    assert result["dap_domain_visits_count"] is None


def test_convert_html_no_content(create_item_with_content):
    html_content = """
    <html lang="en">
    <head>
        <title>Test Article Title</title>
    </head>
    <body>
    </body>
    </html>
    """
    item = create_item_with_content(content=html_content)
    result = transform.convert_html(item=item)

    assert result == {}


def test_convert_html_no_title_or_description(create_item_with_content):
    html_content = """
    <html lang="en">
    <head>
    </head>
    <body>
        <p>This is the main content of the test article.</p>
    </body>
    </html>
    """
    item = create_item_with_content(content=html_content)
    result = transform.convert_html(item=item)
    expected_content = "This is the main content of the test article."
    assert result is not None
    assert result["title_en"] is None
    assert result["description_en"] == expected_content
    assert result["content_en"] == expected_content


def test_convert_html_with_meta_site_name(create_item_with_content):
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
    item = create_item_with_content(content=html_content)
    result = transform.convert_html(item=item)
    assert result is not None
    assert result["title_en"] == "Example Site"  # Uses meta_site_name
    assert "This is the main content." in result["content_en"]


def test_convert_html_with_publish_date(create_item_with_content):
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
    item = create_item_with_content(content=html_content)
    result = transform.convert_html(item=item)
    assert result is not None
    assert result["updated"] is not None  # newspaper4k may or may not parse date from meta; this checks for any value.


def test_convert_html_with_out_publish_date(create_item_with_content):
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
    item = create_item_with_content(content=html_content)
    result = transform.convert_html(item=item)
    assert result is not None
    assert result["updated"] != ""
    assert result["updated"] is None  # newspaper4k may or may not parse date from meta; this checks for any value.


def test_convert_html_languages(create_item_with_content):
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
    item = create_item_with_content(content=html_content, url="https://example.cn/article", lang="zh")
    result = transform.convert_html(item=item)

    assert result is not None
    assert result["content_zh"] == (
        "労化合測断秒化任面件気子人球分向無圧。了作果批入選教済球主運私信成笑論情禁。首着場研打表阪東日善能最囲値名陣必。"
        "想必愛交備見事新演内高青録断狙。詳期斉幕善確込対危継属会提円和動会分子。中常特処秘局創企真刊葉戸獲人師。前場明持二本聞通調写何観。"
        "薫大本設紋証済球取縮不園。辺案惑報湖買含応給奥専申琴真集情月続。"
    )
    assert result["title_zh"] == "Some Title"
    assert result["description_zh"] == content.sanitize_text("这是一个测试描述")
