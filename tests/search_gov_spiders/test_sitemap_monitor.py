import pytest
import hashlib
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock

from search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor import (
    SitemapMonitor,
    create_directory,
)


class MockCrawlSite:
    """A mock CrawlSite class for testing purposes."""

    def __init__(self, starting_urls, sitemap_urls=None, depth_limit=8, check_sitemap_hours=None, **kwargs):
        self.starting_urls = starting_urls
        self.sitemap_urls = sitemap_urls or []
        self.depth_limit = depth_limit
        self.check_sitemap_hours = check_sitemap_hours
        self.handle_javascript = kwargs.get("handle_javascript", False)
        self.allow_query_string = kwargs.get("allow_query_string", False)
        self.allowed_domains = kwargs.get("allowed_domains", [])
        self.deny_paths = kwargs.get("deny_paths", [])
        self.output_target = kwargs.get("output_target", "default")


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory patched into TARGET_DIR."""
    with patch(
        "search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.TARGET_DIR",
        tmp_path,
    ):
        yield tmp_path


def md5_name(url: str) -> str:
    """Helper: hashed filename for a sitemap URL."""
    return hashlib.md5(url.encode()).hexdigest() + ".txt"


# -------------------------------
# create_directory tests
# -------------------------------

def test_create_new_directory(tmp_path):
    target = tmp_path / "foo"
    create_directory(target)
    assert target.is_dir()


def test_create_directory_idempotent(tmp_path):
    target = tmp_path / "bar"
    target.mkdir()
    create_directory(target)
    assert target.is_dir()


# -------------------------------
# SitemapMonitor setup / processing
# -------------------------------

@patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder")
def test_setup_filters_records_by_depth(MockSitemapFinder):
    mock_finder = MockSitemapFinder.return_value
    mock_finder.confirm_sitemap_url.return_value = True
    mock_finder.find.side_effect = lambda url: {f"{url}/sitemap.xml"}

    records = [
        MockCrawlSite(starting_urls="https://example0.com", depth_limit=7),
        MockCrawlSite(starting_urls="https://example1.com", depth_limit=8),
        MockCrawlSite(starting_urls="https://example2.com", depth_limit=9),
    ]
    monitor = SitemapMonitor(records)
    monitor.setup()

    assert len(monitor.all_sitemap_urls) == 2
    assert "https://example1.com/sitemap.xml" in monitor.all_sitemap_urls
    assert "https://example2.com/sitemap.xml" in monitor.all_sitemap_urls
    assert "https://example0.com/sitemap.xml" not in monitor.all_sitemap_urls


@patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder")
def test_process_record_sitemaps_combines_predefined_and_found(MockSitemapFinder):
    mock_finder = MockSitemapFinder.return_value
    mock_finder.confirm_sitemap_url.side_effect = lambda url: url.startswith("https://valid-")
    mock_finder.find.return_value = {"https://discovered.com/sitemap.xml"}

    record = MockCrawlSite(
        starting_urls="https://example.com",
        sitemap_urls=[
            "https://valid-predefined.com/sitemap.xml",
            "https://invalid-predefined.com/sitemap.xml",
        ],
    )
    monitor = SitemapMonitor([])
    result = monitor._process_record_sitemaps(record, mock_finder)

    assert "https://valid-predefined.com/sitemap.xml" in result
    assert "https://discovered.com/sitemap.xml" in result
    assert "https://invalid-predefined.com/sitemap.xml" not in result
    assert len(result) == 2


# -------------------------------
# Stored sitemap load/save
# -------------------------------

def test_load_stored_sitemaps(temp_dir):
    sitemap_url_existing = "https://example.com/existing.xml"
    sitemap_url_new = "https://example.com/new.xml"

    file_path = temp_dir / md5_name(sitemap_url_existing)
    file_path.write_text("https://example.com/url1\nhttps://example.com/url2\n")

    monitor = SitemapMonitor([])
    monitor.all_sitemap_urls = [sitemap_url_existing, sitemap_url_new]
    monitor._load_stored_sitemaps()

    assert monitor.stored_sitemaps[sitemap_url_existing] == {"https://example.com/url1", "https://example.com/url2"}
    assert monitor.is_first_run[sitemap_url_existing] is False
    assert monitor.stored_sitemaps[sitemap_url_new] == set()
    assert monitor.is_first_run[sitemap_url_new] is True


def test_save_sitemap(temp_dir):
    monitor = SitemapMonitor([])
    sitemap_url = "https://example.com/sitemap.xml"
    urls = {"https://example.com/b", "https://example.com/a"}
    monitor._save_sitemap(sitemap_url, urls)

    path = temp_dir / md5_name(sitemap_url)
    saved = path.read_text().splitlines()
    assert saved == ["https://example.com/a", "https://example.com/b"]


# -------------------------------
# _fetch_sitemap tests
# -------------------------------

@patch("requests.Session")
def test_fetch_sitemap_urlset_success(MockSession):
    xml = b"""<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://ex.com/1</loc></url>
                <url><loc>https://ex.com/2</loc></url>
             </urlset>"""
    mock_response = MagicMock(status_code=200, content=xml)
    mock_response.raise_for_status.return_value = None
    mock_session = MockSession.return_value.__enter__.return_value
    mock_session.get.return_value = mock_response

    monitor = SitemapMonitor([])
    result = monitor._fetch_sitemap("https://ex.com/sitemap.xml")

    mock_session.get.assert_called_once_with("https://ex.com/sitemap.xml", timeout=30)
    assert result == {"https://ex.com/1", "https://ex.com/2"}


@patch("requests.Session")
def test_fetch_sitemap_index_recursive(MockSession):
    sitemap_index = b"""<sitemapindex xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
                         <sitemap><loc>https://ex.com/sitemap1.xml</loc></sitemap>
                         <sitemap><loc>https://ex.com/sitemap2.xml</loc></sitemap>
                       </sitemapindex>"""
    sitemap1 = b"<urlset><url><loc>https://ex.com/1</loc></url></urlset>"
    sitemap2 = b"<urlset><url><loc>https://ex.com/2</loc></url></urlset>"

    def mock_get(url, timeout):
        content = {
            "https://ex.com/sitemap.xml": sitemap_index,
            "https://ex.com/sitemap1.xml": sitemap1,
            "https://ex.com/sitemap2.xml": sitemap2,
        }.get(url)
        resp = MagicMock(status_code=200, content=content)
        resp.raise_for_status.return_value = None
        return resp

    mock_session = MockSession.return_value.__enter__.return_value
    mock_session.get.side_effect = mock_get

    monitor = SitemapMonitor([])
    result = monitor._fetch_sitemap("https://ex.com/sitemap.xml")

    assert mock_session.get.call_count == 3
    assert result == {"https://ex.com/1", "https://ex.com/2"}


@patch("requests.Session")
def test_fetch_sitemap_error_returns_empty(MockSession):
    mock_session = MockSession.return_value.__enter__.return_value
    mock_session.get.side_effect = requests.exceptions.RequestException
    monitor = SitemapMonitor([])
    result = monitor._fetch_sitemap("https://fake.url/sitemap.xml")
    assert result == set()


@patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.log")
def test_fetch_sitemap_max_depth(mock_log):
    monitor = SitemapMonitor([])
    monitor._fetch_sitemap("https://fake.url/sitemap.xml", depth=11, max_depth=10)
    mock_log.error.assert_called_with(
        "Maximum recursion depth (10) exceeded for sitemap https://fake.url/sitemap.xml"
    )


# -------------------------------
# _check_for_changes tests
# -------------------------------

@pytest.mark.parametrize(
    "first_run,stored,fetched,expected_new,expected_total",
    [
        (True, set(), {"url1", "url2"}, set(), 2),
        (False, {"url1"}, {"url1", "url2"}, {"url2"}, 2),
        (False, {"url1", "url2"}, {"url1", "url2"}, set(), 2),
    ],
)
def test_check_for_changes(temp_dir, first_run, stored, fetched, expected_new, expected_total, monkeypatch):
    sitemap_url = "https://ex.com/sitemap.xml"
    monitor = SitemapMonitor([])
    monitor.is_first_run[sitemap_url] = first_run
    monitor.stored_sitemaps[sitemap_url] = stored

    monkeypatch.setattr(monitor, "_fetch_sitemap", lambda url: fetched)
    monkeypatch.setattr(monitor, "_save_sitemap", lambda url, urls: None)

    new_urls, total = monitor._check_for_changes(sitemap_url)

    assert new_urls == expected_new
    assert total == expected_total
    assert monitor.is_first_run[sitemap_url] is False
    assert monitor.stored_sitemaps[sitemap_url] == fetched


# -------------------------------
# _get_check_interval tests
# -------------------------------

@patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder")
def test_get_check_interval(MockSitemapFinder):
    mock_finder = MockSitemapFinder.return_value
    mock_finder.confirm_sitemap_url.return_value = True
    mock_finder.find.return_value = set()

    rec1 = MockCrawlSite(
        "https://ex.com",
        sitemap_urls=["https://ex.com/sitemap.xml"],
        check_sitemap_hours=12,
    )
    rec2 = MockCrawlSite(
        "https://default.com",
        sitemap_urls=["https://default.com/sitemap.xml"],
        check_sitemap_hours=None,
    )
    monitor = SitemapMonitor([rec1, rec2])
    monitor.setup()

    assert monitor._get_check_interval("https://ex.com/sitemap.xml") == 12 * 3600
    assert monitor._get_check_interval("https://default.com/sitemap.xml") == 48 * 3600
