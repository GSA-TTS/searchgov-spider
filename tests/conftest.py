import json
from pathlib import Path

import pytest
from search_gov_crawler.search_gov_app.crawl_config import CrawlConfigs


@pytest.fixture(name="crawl_sites_test_file")
def fixture_crawl_sites_test_file() -> Path:
    return Path(__file__).parent / "crawl-sites-test.json"


@pytest.fixture(name="crawl_sites_test_file_json")
def fixture_crawl_sites_test_file_json(crawl_sites_test_file) -> dict:
    return json.loads(crawl_sites_test_file.resolve().read_text())


@pytest.fixture(name="crawl_configs_from_test_file")
def fixture_crawl_configs_from_test_file(crawl_sites_test_file) -> CrawlConfigs:
    return CrawlConfigs.from_file(file=crawl_sites_test_file)
