import subprocess

import pytest

from search_gov_crawler.run.crawl import run_scrapy_crawl


@pytest.mark.parametrize(
    "run_kwargs",
    [
        {
            "spider": "test_spider",
            "allow_query_string": False,
            "allowed_domains": "test-domain.example.com",
            "start_urls": "http://starting-url.example.com/",
            "output_target": "csv",
            "depth_limit": 3,
            "deny_paths": "path",
        }
    ],
)
def test_run_scrapy_crawl(caplog, monkeypatch, run_kwargs):
    def mock_run(*_args, **_kwargs):
        return True

    monkeypatch.setattr(subprocess, "run", mock_run)
    with caplog.at_level("INFO"):
        run_scrapy_crawl(**run_kwargs)

    "Successfully completed scrapy crawl with args spider=%s and kwargs %s"
    assert (
        "Successfully completed scrapy crawl with args spider=test_spider and kwargs {'allow_query_string': False, "
        "'allowed_domains': 'test-domain.example.com', 'start_urls': 'http://starting-url.example.com/', "
        "'output_target': 'csv', 'depth_limit': 3, 'deny_paths': 'path'}"
    ) in caplog.messages
