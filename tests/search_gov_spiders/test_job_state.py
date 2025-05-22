import pytest
import scrapy.settings.default_settings as scrapy_defaults
import scrapy_redis
from scrapy.crawler import Crawler
from scrapy.spiders import Spider
from scrapy.utils.test import get_crawler

from search_gov_crawler.search_gov_spiders.job_state.dupefilter import SearchGovSpiderRedisDupeFilter
from search_gov_crawler.search_gov_spiders.job_state.queue import SearchGovSpiderFifoQueue
from search_gov_crawler.search_gov_spiders.job_state.scheduler import (
    SearchGovSpiderRedisScheduler,
    disable_redis_job_state,
)
from tests.scheduling.conftest import MockRedisClient


@pytest.fixture(name="spider_for_testing")
def fixture_spider_for_testing(project_settings):
    return Spider(
        name="test_spider",
        allowed_domains=["domain 1", "domain 2"],
        start_urls=["url 1", "url 2"],
        settings=project_settings,
        spider_id="testtesttest",
    )


def test_search_gov_spider_fifo_queue(spider_for_testing):
    queue = SearchGovSpiderFifoQueue(
        server=None,
        spider=spider_for_testing,
        key="spider.%(spider)s.requests",
        serializer=None,
    )
    assert queue.key == "spider.testtesttest.requests"


@pytest.fixture(name="redis_crawler")
def fixture_redis_crawler() -> Crawler:
    df_cls_path = "search_gov_crawler.search_gov_spiders.job_state.dupefilter.SearchGovSpiderRedisDupeFilter"
    return get_crawler(
        spidercls=Spider,
        settings_dict={
            "SCHEDULER_QUEUE_KEY": "spider.%(spider)s.requests",
            "SCHEDULER_DUPEFILTER_KEY": "spider.%(spider)s.dupefilter",
            "SCHEDULER_FLUSH_ON_START": True,
            "SCHEDULER_PERSIST": True,
            "DUPEFILTER_CLASS": df_cls_path,
        },
    )


@pytest.fixture(name="redis_scheduler")
def fixture_redis_scheduler(monkeypatch, redis_crawler):
    def mock_redis_client(*_args, **_kwargs):
        return MockRedisClient()

    monkeypatch.setattr(SearchGovSpiderRedisScheduler, "flush", lambda _: True)
    monkeypatch.setattr(scrapy_redis.connection, "from_settings", mock_redis_client)
    return SearchGovSpiderRedisScheduler.from_crawler(redis_crawler)


@pytest.fixture(name="redis_spider_from_crawler")
def fixture_redis_spider_from_crawler(redis_crawler):
    return Spider.from_crawler(
        crawler=redis_crawler,
        name="scheduler_test",
        allowed_domains=["example.com"],
        start_urls=["http://www.example.com"],
        spider_id="testtesttest",
    )


@pytest.mark.filterwarnings("ignore::Warning")  # ignore ScrapyDeprecationWarning
def test_search_gov_spider_redis_scheduler_open(redis_spider_from_crawler, redis_scheduler):
    redis_scheduler.open(redis_spider_from_crawler)
    assert redis_scheduler.queue.key == "spider.testtesttest.requests"


@pytest.mark.parametrize("reason", ["finished", "closespider_test"])
def test_search_gov_spider_redis_scheduler_close(
    caplog, monkeypatch, redis_spider_from_crawler, redis_scheduler, reason
):
    def mock_flush(*_args, **_kwargs):
        redis_spider_from_crawler.logger.info("Flushing Scheduler!")

    monkeypatch.setattr(SearchGovSpiderRedisDupeFilter, "clear", mock_flush)
    redis_scheduler.open(redis_spider_from_crawler)
    with caplog.at_level("INFO"):
        redis_scheduler.close(reason)

    assert "Flushing Scheduler!" in caplog.messages


@pytest.mark.parametrize(
    ("setting", "expected_value"),
    [
        ("SCHEDULER", scrapy_defaults.SCHEDULER),
        ("DUPEFILTER_CLASS", scrapy_defaults.DUPEFILTER_CLASS),
    ],
)
def test_disable_redis_job_state(project_settings, setting, expected_value):
    updated_settings = disable_redis_job_state(project_settings)
    assert updated_settings.get(setting) == expected_value


def test_search_gov_spider_dupe_filter(redis_spider_from_crawler):
    dupefilter = SearchGovSpiderRedisDupeFilter.from_spider(redis_spider_from_crawler)
    assert dupefilter.key == "spider.testtesttest.dupefilter"
