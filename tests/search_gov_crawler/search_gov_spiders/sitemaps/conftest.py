import pytest


@pytest.fixture(name="make_mock_crawl_config")
def fixture_make_mock_crawl_config():
    class MockCrawlConfig:
        """A mock CrawlConfig class for testing purposes."""

        def __init__(self, starting_urls, sitemap_urls, depth_limit, check_sitemap_hours, **kwargs):
            self.starting_urls = starting_urls
            self.sitemap_urls = sitemap_urls or []
            self.depth_limit = depth_limit
            self.check_sitemap_hours = check_sitemap_hours
            self.handle_javascript = kwargs.get("handle_javascript", False)
            self.allow_query_string = kwargs.get("allow_query_string", False)
            self.allowed_domains = kwargs.get("allowed_domains", [])
            self.deny_paths = kwargs.get("deny_paths", [])
            self.output_target = kwargs.get("output_target", "default")

    def _make_mock_crawl_config(starting_urls, sitemap_urls=None, depth_limit=8, check_sitemap_hours=None, **kwargs):
        return MockCrawlConfig(starting_urls, sitemap_urls, depth_limit, check_sitemap_hours, **kwargs)

    return _make_mock_crawl_config


@pytest.fixture(name="mock_finder")
def fixture_mock_finder(mocker):
    return mocker.patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder").return_value
