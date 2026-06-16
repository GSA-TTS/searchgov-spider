import hashlib
from datetime import UTC, datetime

import pytest
import requests
from defusedxml.ElementTree import ParseError
from freezegun import freeze_time

from search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor import SitemapMonitor, create_directory, force_gc


@pytest.fixture
def temp_dir(mocker, tmp_path):
    """Provide a temporary directory patched into TARGET_DIR."""
    return mocker.patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.TARGET_DIR", tmp_path)


def md5_name(url: str) -> str:
    """Helper: hashed filename for a sitemap URL."""
    return hashlib.md5(url.encode()).hexdigest() + ".txt"


def test_create_directory_new(tmp_path):
    target = tmp_path / "foo"
    create_directory(target)
    assert target.is_dir()


def test_create_directory_idempotent(tmp_path):
    target = tmp_path / "bar"
    target.mkdir()
    create_directory(target)
    assert target.is_dir()


@pytest.mark.parametrize("error_cls", [OSError, Exception])
def test_create_directory_error(tmp_path, mocker, error_cls):
    mocker.patch("pathlib.Path.mkdir", side_effect=[error_cls("Error!")])
    with pytest.raises(SystemExit):
        create_directory(tmp_path / "error")


def test_force_gc(mocker):
    mock_collect = mocker.patch("gc.collect")
    force_gc()
    mock_collect.assert_called_once()


def test_setup_filters_records_by_depth(mock_finder, make_mock_crawl_config):
    mock_finder.confirm_sitemap_url.return_value = True
    mock_finder.find.side_effect = lambda url: {f"{url}/sitemap.xml"}

    records = [
        make_mock_crawl_config(starting_urls="https://example0.com", depth_limit=7),
        make_mock_crawl_config(starting_urls="https://example1.com", depth_limit=8),
        make_mock_crawl_config(starting_urls="https://example2.com", depth_limit=9),
    ]
    monitor = SitemapMonitor(records)
    monitor.setup()

    assert len(monitor.all_sitemap_urls) == 2
    assert "https://example1.com/sitemap.xml" in monitor.all_sitemap_urls
    assert "https://example2.com/sitemap.xml" in monitor.all_sitemap_urls
    assert "https://example0.com/sitemap.xml" not in monitor.all_sitemap_urls


@pytest.mark.parametrize(
    "record_kwargs",
    [
        [],
        [
            {"starting_urls": "https://example2.com", "depth_limit": 9},
            {"starting_urls": "https://example2.com", "depth_limit": 10},
        ],
    ],
)
@pytest.mark.usefixtures("mock_finder")
def test_setup_records_filtering(mocker, record_kwargs, make_mock_crawl_config):
    mocker.patch(
        "search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapMonitor._process_record_sitemaps"
    )
    records = [make_mock_crawl_config(**kwargs) for kwargs in record_kwargs]
    monitor = SitemapMonitor(records=records)
    with pytest.raises(SystemExit):
        monitor.setup()


@pytest.fixture(name="empty_sitemap_monitor")
def fixture_empty_sitemap_monitor():
    return SitemapMonitor([])


def test_process_record_sitemaps_combines_predefined_and_found(
    mock_finder, empty_sitemap_monitor, make_mock_crawl_config
):
    mock_finder.confirm_sitemap_url.side_effect = [True, False]
    mock_finder.find.return_value = {"https://discovered.com/sitemap.xml"}

    record = make_mock_crawl_config(
        starting_urls="https://example.com",
        sitemap_urls=[
            "https://valid-predefined.com/sitemap.xml",
            "https://invalid-predefined.com/sitemap.xml",
        ],
    )

    result = empty_sitemap_monitor._process_record_sitemaps(record, mock_finder)
    assert sorted(result) == sorted(["https://valid-predefined.com/sitemap.xml", "https://discovered.com/sitemap.xml"])


def test_load_stored_sitemaps(temp_dir, empty_sitemap_monitor):
    sitemap_url_existing = "https://example.com/existing.xml"
    sitemap_url_new = "https://example.com/new.xml"

    file_path = temp_dir / md5_name(sitemap_url_existing)
    file_path.touch()
    file_path.write_text("https://example.com/url1\nhttps://example.com/url2\n")

    monitor = empty_sitemap_monitor
    monitor.all_sitemap_urls = [sitemap_url_existing, sitemap_url_new]
    monitor._load_stored_sitemaps()

    assert monitor.stored_sitemaps[sitemap_url_existing] == {"https://example.com/url1", "https://example.com/url2"}
    assert monitor.is_first_run[sitemap_url_existing] is False
    assert monitor.stored_sitemaps[sitemap_url_new] == set()
    assert monitor.is_first_run[sitemap_url_new] is True


def test_save_sitemap(temp_dir, empty_sitemap_monitor):
    sitemap_url = "https://example.com/sitemap.xml"
    urls = {"https://example.com/b", "https://example.com/a"}
    empty_sitemap_monitor._save_sitemap(sitemap_url, urls)

    path = temp_dir / md5_name(sitemap_url)
    saved = path.read_text().splitlines()
    assert saved == ["https://example.com/a", "https://example.com/b"]


def test_save_sitemap_no_urls(empty_sitemap_monitor):
    assert empty_sitemap_monitor._save_sitemap("https://example.com/sitemap.xml", set()) is None


def test_save_sitemap_error(caplog, mocker, empty_sitemap_monitor):
    mocker.patch("pathlib.Path.open", side_effect=[Exception("No Way!")])
    with caplog.at_level("INFO"):
        empty_sitemap_monitor._save_sitemap(
            "https://www.example.com", {"https://example.com/b", "https://example.com/a"}
        )

    assert "Error saving sitemap for https://www.example.com" in caplog.messages


def test_fetch_sitemap_urlset_success(mocker, empty_sitemap_monitor):
    mock_session = mocker.patch("requests.Session").return_value.__enter__.return_value
    xml = b"""<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
                <url><loc>https://ex.com/1</loc></url>
                <url><loc>https://ex.com/2</loc></url>
             </urlset>"""
    mock_response = mocker.MagicMock(status_code=200, content=xml)
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response

    result = empty_sitemap_monitor._fetch_sitemap("https://ex.com/sitemap.xml")

    mock_session.get.assert_called_once_with("https://ex.com/sitemap.xml", timeout=30)
    assert result == {"https://ex.com/1", "https://ex.com/2"}


def test_fetch_sitemap_index_recursive(mocker, empty_sitemap_monitor):
    sitemap_index = b"""<sitemapindex xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
                         <sitemap><loc>https://ex.com/sitemap1.xml</loc></sitemap>
                         <sitemap><loc>https://ex.com/sitemap2.xml</loc></sitemap>
                       </sitemapindex>"""
    sitemap1 = b"<urlset><url><loc>https://ex.com/1</loc></url></urlset>"
    sitemap2 = b"<urlset><url><loc>https://ex.com/2</loc></url></urlset>"

    def mock_get(url, timeout):  # noqa: ARG001
        content = {
            "https://ex.com/sitemap.xml": sitemap_index,
            "https://ex.com/sitemap1.xml": sitemap1,
            "https://ex.com/sitemap2.xml": sitemap2,
        }.get(url)
        resp = mocker.MagicMock(status_code=200, content=content)
        resp.raise_for_status.return_value = None
        return resp

    mock_session = mocker.patch("requests.Session").return_value.__enter__.return_value
    mock_session.get.side_effect = mock_get

    result = empty_sitemap_monitor._fetch_sitemap("https://ex.com/sitemap.xml")

    assert mock_session.get.call_count == 3
    assert result == {"https://ex.com/1", "https://ex.com/2"}


def test_fetch_sitemap_error_returns_empty(mocker, empty_sitemap_monitor):
    mock_session = mocker.patch("requests.Session").return_value.__enter__.return_value
    mock_session.get.side_effect = requests.exceptions.RequestException
    result = empty_sitemap_monitor._fetch_sitemap("https://fake.url/sitemap.xml")
    assert result == set()


@pytest.mark.parametrize(
    ("exception_cls", "error_msg"),
    [(ParseError, "Error parsing sitemap XML from"), (Exception, "Unexpected error processing sitemap")],
)
def test_fetch_sitemap_other_errors(mocker, caplog, empty_sitemap_monitor, exception_cls, error_msg):
    mocker.patch("requests.Session")
    mocker.patch(
        "search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.fromstring",
        side_effect=[exception_cls("Womp womp...")],
    )
    with caplog.at_level("INFO"):
        empty_sitemap_monitor._fetch_sitemap("https://fake.url/sitemap.xml")

    assert f"{error_msg} https://fake.url/sitemap.xml" in caplog.messages


def test_fetch_sitemap_max_depth(mocker, empty_sitemap_monitor):
    mock_log = mocker.patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.log")
    empty_sitemap_monitor._fetch_sitemap("https://fake.url/sitemap.xml", depth=11, max_depth=10)
    mock_log.error.assert_called_with(
        "Maximum recursion depth (%s) exceeded for sitemap %s",
        10,
        "https://fake.url/sitemap.xml",
    )


# -------------------------------
# _check_for_changes tests
# -------------------------------


@pytest.mark.parametrize(
    ("first_run", "stored", "fetched", "expected_new", "expected_total"),
    [
        (True, set(), {"url1", "url2"}, set(), 2),
        (False, {"url1"}, {"url1", "url2"}, {"url2"}, 2),
        (False, {"url1", "url2"}, {"url1", "url2"}, set(), 2),
    ],
)
def test_check_for_changes(
    empty_sitemap_monitor, first_run, stored, fetched, expected_new, expected_total, monkeypatch
):
    sitemap_url = "https://ex.com/sitemap.xml"
    monitor = empty_sitemap_monitor
    monitor.is_first_run[sitemap_url] = first_run
    monitor.stored_sitemaps[sitemap_url] = stored

    monkeypatch.setattr(monitor, "_fetch_sitemap", lambda _url: fetched)
    monkeypatch.setattr(monitor, "_save_sitemap", lambda _url, _urls: None)

    new_urls, total = monitor._check_for_changes(sitemap_url)

    assert new_urls == expected_new
    assert total == expected_total
    assert monitor.is_first_run[sitemap_url] is False
    assert monitor.stored_sitemaps[sitemap_url] == fetched


def test_get_check_interval(mocker, make_mock_crawl_config):
    mock_finder = mocker.patch(
        "search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder",
    ).return_value
    mock_finder.confirm_sitemap_url.return_value = True
    mock_finder.find.return_value = set()

    rec1 = make_mock_crawl_config(
        "https://ex.com",
        sitemap_urls=["https://ex.com/sitemap.xml"],
        check_sitemap_hours=12,
    )
    rec2 = make_mock_crawl_config(
        "https://default.com",
        sitemap_urls=["https://default.com/sitemap.xml"],
        check_sitemap_hours=None,
    )
    monitor = SitemapMonitor([rec1, rec2])
    monitor.setup()

    assert monitor._get_check_interval("https://ex.com/sitemap.xml") == 12 * 3600
    assert monitor._get_check_interval("https://default.com/sitemap.xml") == 48 * 3600


@freeze_time("2026-01-02 01:23:34", tz_offset=0)
def test_run(mocker, make_mock_crawl_config):
    mocker.patch("time.sleep")
    mocker.patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapMonitor.setup")
    mocker.patch(
        "search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapMonitor._get_check_interval",
        return_value=10,
    )
    mocker.patch(
        "search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapMonitor._check_for_changes",
        side_effect=[({"https://1.example.com/page1", "https://1.example.com/page2"}, 2), KeyboardInterrupt()],
    )
    mock_spider_process = mocker.patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.Process")

    monitor = SitemapMonitor(records=[])
    monitor.all_sitemap_urls = ["https://1.example.com/sitemap.xml", "https://2.example.com/sitemap.xml"]
    monitor.next_check_times = {
        "https://1.example.com/sitemap.xml": datetime.now(tz=UTC).timestamp(),
        "https://2.example.com/sitemap.xml": datetime.now(tz=UTC).timestamp(),
    }
    monitor.records_map = {
        "https://1.example.com/sitemap.xml": make_mock_crawl_config(starting_urls="https://example0.com", depth_limit=2)
    }

    monitor.run()
    mock_spider_process.return_value.start.assert_called_once()
