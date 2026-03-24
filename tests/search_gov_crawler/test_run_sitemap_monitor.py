import pytest
from pathlib import Path
from search_gov_crawler.run_sitemap_monitor import start_sitemap_monitor


def test_start_sitemap_monitor_missing_input_file(mocker):
    mocker.patch("pathlib.Path.exists", return_value=False)
    input_file = Path("invalid_file.json")

    with pytest.raises(
        FileNotFoundError,
        match=f"Cannot start sitemap monitor! Input file {input_file} does not exist.",
    ):
        start_sitemap_monitor(input_file=input_file)


def test_start_sitemap_monitor_exception(mocker):
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("search_gov_crawler.run_sitemap_monitor.CrawlConfigs.from_file")
    mock_monitor = mocker.patch("search_gov_crawler.run_sitemap_monitor.SitemapMonitor")
    mock_monitor.side_effect = Exception("Test exception")

    with pytest.raises(Exception, match="Test exception"):
        start_sitemap_monitor(input_file=Path("valid_file.json"))


def test_start_sitemap_monitor(mocker):
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch("search_gov_crawler.run_sitemap_monitor.CrawlConfigs.from_file")
    mock_monitor = mocker.patch("search_gov_crawler.run_sitemap_monitor.SitemapMonitor")

    start_sitemap_monitor(input_file=Path("valid_file.json"))
    mock_monitor.return_value.run.assert_called_once()
