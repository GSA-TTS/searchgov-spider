import json
import sys
import tempfile
from pathlib import Path

import pytest
from scrapy.crawler import CrawlerProcess

from search_gov_crawler.search_gov_spiders.job_state.scheduler import disable_redis_job_state
from search_gov_crawler.search_gov_spiders.spiders.domain_spider import DomainSpider
from search_gov_crawler.search_gov_spiders.spiders.domain_spider_js import (
    DomainSpiderJs,
)


@pytest.fixture(name="mock_scrapy_settings")
def fixture_mock_scrapy_settings(project_settings):
    project_settings.set("SPIDER_MODULES", ["search_gov_crawler.search_gov_spiders.spiders"])
    project_settings.set(
        "SPIDER_MIDDLEWARES",
        {f"search_gov_crawler.{k}": v for k, v in dict(project_settings.get("SPIDER_MIDDLEWARES").attributes).items()},
    )
    project_settings.set(
        "DOWNLOADER_MIDDLEWARES",
        {
            f"search_gov_crawler.{k}": v
            for k, v in dict(project_settings.get("DOWNLOADER_MIDDLEWARES").attributes).items()
        },
    )
    project_settings.set("EXTENSIONS", {})
    project_settings.set("JOBDIR", None)
    project_settings.set("HTTPCACHE_ENABLED", True)
    project_settings.set("HTTPCACHE_DBM_MODULE", "dbm.dumb")
    project_settings.set("HTTPCACHE_DIR", Path(__file__).parent.joinpath("scrapy_httpcache"))
    project_settings.set("HTTPCACHE_STORAGE", "scrapy.extensions.httpcache.DbmCacheStorage")
    project_settings.set("DEPTH_LIMIT", 0)

    # Ensures cache does not change, set to False if you need to update or replace cache files
    project_settings.set("HTTPCACHE_IGNORE_MISSING", True)

    # Disable scrapy-redis
    project_settings = disable_redis_job_state(project_settings)

    yield project_settings

    try:
        del sys.modules["twisted.internet.reactor"]
        del sys.modules["twisted.internet"]
    except KeyError:  # pragma: no cover
        pass


FULL_CRAWL_TEST_CASES = [
    (
        DomainSpider,
        False,
        {
            "allow_query_string": False,
            "allowed_domains": "quotes.toscrape.com",
            "start_urls": "https://quotes.toscrape.com/",
            "output_target": "csv",
            "depth_limit": 20,
            "deny_paths": None,
        },
        378,
    ),
    (
        DomainSpider,
        False,
        {
            "allow_query_string": False,
            "allowed_domains": "quotes.toscrape.com",
            "start_urls": "https://quotes.toscrape.com/",
            "output_target": "csv",
            "depth_limit": 20,
            "deny_paths": "/tag/",
        },
        74,
    ),
    (
        DomainSpider,
        False,
        {
            "allow_query_string": False,
            "allowed_domains": "quotes.toscrape.com/tag/",
            "start_urls": "https://quotes.toscrape.com/",
            "output_target": "csv",
            "depth_limit": 20,
            "deny_paths": None,
        },
        120,
    ),
    (
        DomainSpiderJs,
        True,
        {
            "allow_query_string": False,
            "allowed_domains": "quotes.toscrape.com",
            "start_urls": "https://quotes.toscrape.com/js/",
            "output_target": "endpoint",
            "depth_limit": 20,
            "deny_paths": None,
        },
        0,
    ),
    (
        DomainSpiderJs,
        True,
        {
            "allow_query_string": False,
            "allowed_domains": "quotes.toscrape.com/js/",
            "start_urls": "https://quotes.toscrape.com/js/",
            "output_target": "endpoint",
            "depth_limit": 20,
            "deny_paths": None,
        },
        0,
    ),
]


@pytest.mark.parametrize(("spider", "use_dedup", "crawl_kwargs", "expected_results"), FULL_CRAWL_TEST_CASES)
def test_full_crawl(mock_scrapy_settings, monkeypatch, spider, use_dedup, crawl_kwargs, expected_results):
    # only use dedup pipeline for js test, otherwise dupes are not cleared between runs
    mock_scrapy_settings.set(
        "ITEM_PIPELINES",
        {
            f"search_gov_crawler.{k}": v
            for k, v in dict(mock_scrapy_settings.get("ITEM_PIPELINES")).items()
            if (k == "search_gov_spiders.pipelines.SearchGovSpidersPipeline" or use_dedup)
        },
    )

    max_file_size = 3900  # intentionally kept low to allow for paging of files in small dataset

    with tempfile.NamedTemporaryFile(suffix=".json") as output_file:
        temp_dir = Path(str(output_file.name)).parent
        temp_dir.joinpath("output").mkdir(exist_ok=True)

        def mock_init(pipeline_cls, *_args, temp_dir=temp_dir, **_kwargs):
            pipeline_cls.api_url = None
            pipeline_cls.file_number = 1
            pipeline_cls.parent_file_path = temp_dir
            pipeline_cls.base_file_name = temp_dir / "output" / "all-links-p1234.csv"
            pipeline_cls.file_path = pipeline_cls.base_file_name
            pipeline_cls.current_file = open(pipeline_cls.file_path, "w", encoding="utf-8")
            pipeline_cls.file_open = False
            pipeline_cls._es = None
            pipeline_cls.urls_batch = []

        monkeypatch.setattr(
            "search_gov_crawler.search_gov_spiders.pipelines.SearchGovSpidersPipeline.__init__",
            mock_init,
        )

        mock_scrapy_settings.set("FEEDS", {output_file.name: {"format": "json"}})

        process = CrawlerProcess(mock_scrapy_settings, install_root_handler=False)
        process.crawl(spider, **crawl_kwargs)
        process.start()

        with open(output_file.name, encoding="UTF") as f:
            links = json.load(f)

        split_files = list(temp_dir.glob("all-links-p*.csv"))

        # verify total links match expected
        assert len(links) == expected_results

        # verify split files exist and are under max file size
        assert all(split_file.stat().st_size < max_file_size for split_file in split_files)
