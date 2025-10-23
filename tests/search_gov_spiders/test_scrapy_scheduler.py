import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from apscheduler.triggers.cron import CronTrigger
from elasticsearch import Elasticsearch

from search_gov_crawler.scheduling.jobstores import SpiderRedisJobStore
from search_gov_crawler.scrapy_scheduler import (
    init_scheduler,
    run_scrapy_crawl,
    start_scrapy_scheduler,
    transform_crawl_configs,
    wait_for_next_interval,
)


@pytest.fixture(name="mock_es_client")
def fixtture_mock_es_client() -> MagicMock:
    client = MagicMock(spec=Elasticsearch)
    client.indices = MagicMock()
    client.indices.exists = MagicMock()
    client.indices.create = MagicMock()
    return client


@pytest.fixture(name="mock_jobstore")
def fixture_mock_jobstore() -> MagicMock:
    jobstore = MagicMock(spec=SpiderRedisJobStore)
    jobstore.get_due_jobs = MagicMock(return_value=[])
    return jobstore


@pytest.mark.parametrize(
    "run_args",
    [("test_spider", False, "test-domain.example.com", "http://starting-url.example.com/", "csv", 3, "path")],
)
def test_run_scrapy_crawl(caplog, monkeypatch, run_args):
    def mock_run(*_args, **_kwargs):
        return True

    monkeypatch.setattr(subprocess, "run", mock_run)
    with caplog.at_level("INFO"):
        run_scrapy_crawl(*run_args)

    assert (
        "Successfully completed scrapy crawl with args spider=test_spider, allow_query_string=False, "
        "allowed_domains=test-domain.example.com, start_urls=http://starting-url.example.com/, "
        "output_target=csv, depth_limit=3, deny_paths=path"
    ) in caplog.messages


@pytest.mark.parametrize(
    ("test_kwargs", "expected"),
    [({"interval": 0}, True), ({"interval": 0, "keep_running": False}, False)],
)
def test_wait_for_next_interval(caplog, test_kwargs, expected):
    with caplog.at_level("DEBUG"):
        result = wait_for_next_interval(**test_kwargs)

    assert result is expected
    assert f"Woke up after sleeping for {test_kwargs['interval']} seconds" in caplog.messages


def test_transform_crawl_configs(crawl_configs_from_test_file):
    transformed_crawl_configs = transform_crawl_configs(crawl_configs_from_test_file)

    # CronTrigger class does not implement __eq__
    triggers = [str(site.pop("trigger")) for site in transformed_crawl_configs]
    for trigger in triggers:
        assert trigger == str(
            CronTrigger(
                month="*",
                day="*",
                day_of_week="*",
                hour="*",
                minute="0,15,30,45",
                timezone="UTC",
            ),
        )

    assert transformed_crawl_configs == [
        {
            "func": run_scrapy_crawl,
            "id": "quotes-1",
            "name": "Quotes 1",
            "args": ["domain_spider", False, "quotes.toscrape.com", "https://quotes.toscrape.com/", "csv", 3, []],
        },
        {
            "func": run_scrapy_crawl,
            "id": "quotes-2",
            "name": "Quotes 2",
            "args": [
                "domain_spider_js",
                False,
                "quotes.toscrape.com/js",
                "https://quotes.toscrape.com/js/",
                "csv",
                3,
                [],
            ],
        },
        {
            "func": run_scrapy_crawl,
            "id": "quotes-3",
            "name": "Quotes 3",
            "args": [
                "domain_spider_js",
                False,
                "quotes.toscrape.com/js-delayed",
                "https://quotes.toscrape.com/js-delayed/",
                "endpoint",
                3,
                ["/author/", "/tag/"],
            ],
        },
        {
            "func": run_scrapy_crawl,
            "id": "quotes-4",
            "name": "Quotes 4",
            "args": [
                "domain_spider",
                False,
                "quotes.toscrape.com/tag/",
                "https://quotes.toscrape.com/tag/love/",
                "endpoint",
                3,
                ["/author/"],
            ],
        },
    ]


@pytest.mark.parametrize(("scrapy_max_workers", "expected_val"), [("100", 100), (None, 5)])
def test_init_scheduler(caplog, monkeypatch, scrapy_max_workers, expected_val, mock_jobstore):
    if scrapy_max_workers:
        monkeypatch.setenv("SPIDER_SCRAPY_MAX_WORKERS", scrapy_max_workers)
    else:
        monkeypatch.delenv("SPIDER_SCRAPY_MAX_WORKERS", raising=False)

    monkeypatch.setattr(os, "cpu_count", lambda: 10)

    with (
        caplog.at_level("INFO"),
        patch("search_gov_crawler.scrapy_scheduler.SpiderRedisJobStore", return_value=mock_jobstore),
    ):
        scheduler = init_scheduler()

    # ensure config does not change without a failure here
    assert scheduler._job_defaults == {
        "misfire_grace_time": None,
        "coalesce": True,
        "max_instances": 1,
    }
    assert list(scheduler._jobstores.keys()) == ["redis"]
    assert f"Max workers for schedule set to {expected_val}" in caplog.messages


def test_start_scrapy_scheduler_bad_initialization(caplog, monkeypatch):
    def raise_error(*_args, **_kwargs):
        msg = "Sorry database is down!"
        raise ValueError(msg)

    monkeypatch.setattr("search_gov_crawler.scrapy_scheduler.CrawlConfigs.from_database", raise_error)
    monkeypatch.setenv("SPIDER_CRAWL_CONFIGS_CHECK_INTERVAL", "0")
    monkeypatch.setattr("search_gov_crawler.scrapy_scheduler.wait_for_next_interval", lambda interval: False)
    with caplog.at_level("ERROR"):
        start_scrapy_scheduler()

    assert "Error initializing scheduler!" in caplog.messages


def test_start_scrapy_scheduler(caplog, monkeypatch, crawl_configs_from_test_file, mock_es_client, mock_jobstore):
    def mock_from_database():
        return crawl_configs_from_test_file

    def mock_wait_for_next_interval(*_args, **_kwargs):
        yield from [True, False]

    monkeypatch.setattr("search_gov_crawler.scrapy_scheduler.CrawlConfigs.from_database", mock_from_database)
    monkeypatch.setattr("search_gov_crawler.scrapy_scheduler.SpiderBackgroundScheduler.resume", lambda _: True)
    monkeypatch.setattr("search_gov_crawler.scrapy_scheduler.wait_for_next_interval", mock_wait_for_next_interval)

    with (
        caplog.at_level("INFO"),
        patch(
            "search_gov_crawler.search_engines.es_batch_upload.SearchGovElasticsearch.client",
            return_value=mock_es_client,
        ),
        patch("search_gov_crawler.scrapy_scheduler.SpiderRedisJobStore", return_value=mock_jobstore),
    ):
        start_scrapy_scheduler()

        messages = [f'Added job "Quotes {job_num}" to job store "redis"' for job_num in range(1, 5)]
        assert all(message in caplog.messages for message in messages)
