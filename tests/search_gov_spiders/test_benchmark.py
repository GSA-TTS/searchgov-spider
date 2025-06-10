import os
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from elasticsearch import Elasticsearch
from freezegun import freeze_time

from search_gov_crawler import scrapy_scheduler
from search_gov_crawler.benchmark import (
    benchmark_from_args,
    benchmark_from_file,
    create_apscheduler_job,
    init_scheduler,
)


@pytest.fixture
def mock_es_client():
    client = MagicMock(spec=Elasticsearch)
    client.indices = MagicMock()
    client.indices.exists = MagicMock()
    client.indices.create = MagicMock()
    return client


@pytest.mark.parametrize(("scrapy_max_workers", "expected_val"), [("100", 100), (None, 5)])
def test_init_scheduler(caplog, monkeypatch, scrapy_max_workers, expected_val):
    if scrapy_max_workers:
        monkeypatch.setenv("SPIDER_SCRAPY_MAX_WORKERS", scrapy_max_workers)
    else:
        monkeypatch.delenv("SPIDER_SCRAPY_MAX_WORKERS", raising=False)

    monkeypatch.setattr(os, "cpu_count", lambda: 10)

    with caplog.at_level("INFO"):
        scheduler = init_scheduler()

    # ensure config does not change without a failure here
    assert scheduler._job_defaults == {
        "misfire_grace_time": None,
        "coalesce": True,
        "max_instances": 1,
    }
    assert f"Max workers for schedule set to {expected_val}" in caplog.messages


@freeze_time("2024-01-01 00:00:00", tz_offset=0)
@pytest.mark.parametrize(
    ("handle_javascript", "spider_arg"),
    [(True, "domain_spider_js"), (False, "domain_spider")],
)
def test_create_apscheduler_job(handle_javascript, spider_arg):
    test_args = {
        "name": "test",
        "allow_query_string": True,
        "allowed_domains": "example.com",
        "starting_urls": "https://www.example.com",
        "handle_javascript": handle_javascript,
        "output_target": "csv",
        "runtime_offset_seconds": 5,
        "depth_limit": 3,
        "deny_paths": "/deny-path1/,/deny-path2/",
    }

    assert create_apscheduler_job(**test_args) == {
        "func": scrapy_scheduler.run_scrapy_crawl,
        "id": f"benchmark - {test_args['name']}",
        "name": f"benchmark - {test_args['name']}",
        "next_run_time": datetime(2024, 1, 1, 0, 0, 5, tzinfo=UTC),
        "args": [
            spider_arg,
            test_args["allow_query_string"],
            test_args["allowed_domains"],
            test_args["starting_urls"],
            test_args["output_target"],
            test_args["depth_limit"],
            test_args["deny_paths"],
        ],
    }


class MockScheduler:
    @staticmethod
    def add_job(*_args, **_kwargs):
        return True

    @staticmethod
    def start():
        return True

    @staticmethod
    def shutdown():
        return True


def test_benchmark_from_args(caplog, monkeypatch, mock_es_client):
    with patch(
        "search_gov_crawler.elasticsearch.es_batch_upload.SearchGovElasticsearch._get_client",
        return_value=mock_es_client,
    ):
        monkeypatch.setattr(time, "sleep", lambda x: True)
        monkeypatch.setattr("search_gov_crawler.benchmark.init_scheduler", lambda: MockScheduler())  # pylint: disable=unnecessary-lambda
        test_args = {
            "allow_query_string": True,
            "allowed_domains": "unit-test.example.com",
            "starting_urls": "https://unit-test.example.com",
            "handle_javascript": False,
            "output_target": "csv",
            "runtime_offset_seconds": 0,
            "depth_limit": 3,
            "deny_paths": "/deny-path1/,/deny-path2/",
        }
        with caplog.at_level("INFO"):
            benchmark_from_args(**test_args)

        expected_log_msg = (
            "Starting benchmark from args! allow_query_string=True allowed_domains=unit-test.example.com "
            "starting_urls=https://unit-test.example.com handle_javascript=False output_target=csv "
            "runtime_offset_seconds=0 depth_limit=3 deny_paths=/deny-path1/,/deny-path2/"
        )
        assert expected_log_msg in caplog.messages


def test_benchmark_from_file(caplog, monkeypatch, mock_es_client):
    with patch(
        "search_gov_crawler.elasticsearch.es_batch_upload.SearchGovElasticsearch._get_client",
        return_value=mock_es_client,
    ):
        monkeypatch.setattr(time, "sleep", lambda x: True)
        monkeypatch.setattr("search_gov_crawler.benchmark.init_scheduler", lambda: MockScheduler())  # pylint: disable=unnecessary-lambda

        input_file = Path(__file__).parent / "crawl-sites-test.json"
        with caplog.at_level("INFO"):
            benchmark_from_file(input_file=input_file, runtime_offset_seconds=0)

        assert (
            "Starting benchmark from file! input_file=crawl-sites-test.json runtime_offset_seconds=0" in caplog.messages
        )


def test_benchmark_from_file_missing_file():
    input_file = Path("/does/not/exist.json")
    with pytest.raises(FileNotFoundError, match=f"Input file {input_file} does not exist!"):
        benchmark_from_file(input_file=input_file, runtime_offset_seconds=0)
