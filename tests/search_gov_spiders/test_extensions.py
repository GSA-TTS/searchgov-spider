import io
import json
import logging
import tempfile
from pathlib import Path

import pytest
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured
from scrapy.spiders import Spider

from search_gov_crawler.search_gov_spiders.extensions.json_logging import (
    JsonLogging,
    SearchGovSpiderFileHandler,
    SearchGovSpiderStreamHandler,
)
from search_gov_crawler.search_gov_spiders.extensions.scheduler_queue import OnDiskSchedulerQueue, RedisSchedulerQueue
from tests.scheduling.conftest import MockRedisClient


class SpiderForTest(Spider):
    """Mock spider to support extension testing"""

    spider_id = "testtesttest"

    def __repr__(self):
        return str(
            {
                "allow_query_string": getattr(self, "allow_query_string", None),
                "allowed_domain_paths": getattr(self, "allowed_domain_paths", None),
                "allowed_domains": getattr(self, "allowed_domains", None),
                "name": self.name,
                "spider_id": self.spider_id,
                "start_urls": self.start_urls,
                "output_target": getattr(self, "output_target", None),
                "deny_paths": getattr(self, "_deny_paths", None),
            },
        )


HANDLER_TEST_CASES = [
    ("This is a test message!!", "This is a test message!!", None, None),
    (
        SpiderForTest(
            name="handler_test",
            allow_query_string=False,
            allowed_domain_paths=None,
            allowed_domains="example.com",
            start_urls="https://www.example.com",
            output_target="csv",
            _deny_paths=None,
        ),
        str(
            {
                "allow_query_string": False,
                "allowed_domain_paths": None,
                "allowed_domains": "example.com",
                "name": "handler_test",
                "spider_id": "testtesttest",
                "start_urls": "https://www.example.com",
                "output_target": "csv",
                "deny_paths": None,
            },
        ),
        SpiderForTest(
            name="handler_test",
            allow_query_string=True,
            allowed_domain_paths=None,
            allowed_domains="example.com",
            start_urls="https://www.example.com",
            output_target="csv",
            _deny_paths=None,
        ),
        {
            "allow_query_string": True,
            "allowed_domain_paths": None,
            "allowed_domains": "example.com",
            "name": "handler_test",
            "spider_id": "testtesttest",
            "start_urls": "https://www.example.com",
            "output_target": "csv",
            "deny_paths": None,
            "depth_limit": 3,
        },
    ),
]


@pytest.mark.parametrize(("input_message", "logged_message", "input_object", "logged_object"), HANDLER_TEST_CASES)
def test_stream_hanlder(project_settings, input_message, logged_message, input_object, logged_object):
    log_stream = io.StringIO()
    log = logging.getLogger("test_stream_hanlder")
    log.setLevel(logging.INFO)
    log.addHandler(SearchGovSpiderStreamHandler(log_level=logging.INFO, stream=log_stream))

    if isinstance(input_object, Spider):
        input_object.settings = project_settings
    log.info(input_message, extra={"scrapy_object": input_object})

    log_message = json.loads(log_stream.getvalue().rstrip("\n"))
    assert list(log_message.keys()) == ["asctime", "name", "levelname", "message", "scrapy_object"]
    assert log_message["message"] == logged_message
    assert log_message["scrapy_object"] == logged_object


@pytest.mark.parametrize(("input_message", "logged_message", "input_object", "logged_object"), HANDLER_TEST_CASES)
def test_file_handler(input_message, logged_message, input_object, logged_object):
    with tempfile.NamedTemporaryFile() as temp_file:
        log = logging.getLogger("test_stream_hanlder")
        log.setLevel(logging.INFO)
        log.addHandler(SearchGovSpiderFileHandler(log_level="INFO", filename=temp_file.name))

        log.info(input_message, extra={"scrapy_object": input_object})

        log_message = json.load(temp_file)

    assert list(log_message.keys()) == ["asctime", "name", "levelname", "message", "scrapy_object"]
    assert log_message["message"] == logged_message
    assert log_message["scrapy_object"] == logged_object


def test_file_handler_from_handler():
    with tempfile.NamedTemporaryFile() as temp_file:
        spider_file_hanlder = SearchGovSpiderFileHandler.from_hanlder(
            handler=logging.FileHandler(temp_file.name, mode="w", encoding="ASCII", delay=True, errors="test"),
            log_level="INFO",
        )

        assert spider_file_hanlder.baseFilename == f"{temp_file.name}.json"
        assert spider_file_hanlder.mode == "w"
        assert spider_file_hanlder.encoding == "ASCII"
        assert spider_file_hanlder.delay is True
        assert spider_file_hanlder.errors == "test"


def test_extension_init():
    log = logging.getLogger()
    log.setLevel(logging.INFO)

    extension = JsonLogging(log_level=logging.INFO)
    assert extension.file_hanlder_enabled is True
    assert any(isinstance(handler, SearchGovSpiderStreamHandler) for handler in log.handlers)


@pytest.mark.parametrize(
    ("extension_cls", "extension_settings", "error_message"),
    [
        (
            JsonLogging,
            ("JSON_LOGGING_ENABLED", False),
            "JsonLogging extension is listed in settings.EXTENSIONS but is not enabled.",
        ),
        (
            OnDiskSchedulerQueue,
            ("JOBDIR", None),
            "OnDiskSchedulerQueue extension is listed in settings.EXTENSIONS but JOBDIR is not set.",
        ),
        (
            RedisSchedulerQueue,
            ("SCHEDULER_PERSIST", False),
            "RedisSchedulerQueue extension is listed in settings.EXTENSIONS but SCHEDULER_PERSIST is not True.",
        ),
        (
            RedisSchedulerQueue,
            ("SCHEDULER_KEY_ORPHAN_AGE", None),
            "RedisSchedulerQueue extension is listed in settings.EXTENSIONS but SCHEDULER_KEY_ORPHAN_AGE is not set.",
        ),
        (
            RedisSchedulerQueue,
            ("SCHEDULER_DUPEFILTER_KEY", None),
            (
                "RedisSchedulerQueue extension is listed in settings.EXTENSIONS but "
                "SCHEDULER_DUPEFILTER_KEY or SCHEDULER_QUEUE_KEY is not set"
            ),
        ),
        (
            RedisSchedulerQueue,
            ("SCHEDULER_QUEUE_KEY", None),
            (
                "RedisSchedulerQueue extension is listed in settings.EXTENSIONS but "
                "SCHEDULER_DUPEFILTER_KEY or SCHEDULER_QUEUE_KEY is not set"
            ),
        ),
    ],
)
def test_extension_from_crawler_not_configured(project_settings, extension_cls, extension_settings, error_message):
    project_settings.set(*extension_settings)

    with pytest.raises(NotConfigured, match=error_message):
        extension_cls.from_crawler(Crawler(spidercls=Spider, settings=project_settings))


@pytest.mark.parametrize("extension_cls", [JsonLogging, OnDiskSchedulerQueue])
def test_extension_from_crawler(project_settings, extension_cls):
    project_settings.set("JOBDIR", "/some/test/value/")
    extension = extension_cls.from_crawler(Crawler(spidercls=Spider, settings=project_settings))
    assert isinstance(extension, extension_cls)


def test_extension_spider_opened(caplog, project_settings):
    log = logging.getLogger("test_spider")
    log.setLevel(logging.INFO)

    spider = Spider(
        name="test_spider",
        spider_id="testtesttest",
        allowed_domains=["domain 1", "domain 2"],
        start_urls=["url 1", "url 2"],
        output_target="csv",
        settings=project_settings,
        _deny_paths="path1",
    )
    extension = JsonLogging(log_level=logging.INFO)
    with caplog.at_level(logging.INFO):
        extension.spider_opened(spider)

    assert (
        "Starting spider test_spider (spider_id testtesttest) with following args: "
        "allowed_domains=domain 1,domain 2 allowed_domain_paths= start_urls=url 1,url 2 "
        "output_target=csv depth_limit=3 deny_paths=path1"
    ) in caplog.messages


def test_extension_spider_closed(project_settings):
    spider = Spider(
        name="test_spider",
        allowed_domains=["domain 1", "domain 2"],
        start_urls=["url 1", "url 2"],
        settings=project_settings,
    )

    # setup temp dir as JOBDIR, populated and cleanup
    with tempfile.TemporaryDirectory() as temp_dir:
        job_dir = Path(temp_dir) / "test-job"
        spider.settings.set("JOBDIR", str(job_dir))
        job_dir.mkdir()
        Path(job_dir / "test-file.txt").touch()
        sub_directory = Path(job_dir / "test-dir")
        sub_directory.mkdir()
        Path(sub_directory / "test-file.txt").touch()

        extension = OnDiskSchedulerQueue()
        extension.spider_closed(spider)

        assert not job_dir.exists()


def test_redis_scheduler_spider_closed(project_settings, monkeypatch, caplog):
    def mock_redis_client(*_args, **_kwargs):
        return MockRedisClient()

    def mock_is_orphan_key(*_args, **_kwargs):
        return True

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_spiders.extensions.scheduler_queue.init_redis_client",
        mock_redis_client,
    )
    monkeypatch.setattr(RedisSchedulerQueue, "_is_orphan_key", mock_is_orphan_key)
    spider = Spider(
        name="test_spider",
        allowed_domains=["domain 1", "domain 2"],
        start_urls=["url 1", "url 2"],
        settings=project_settings,
    )

    extension = RedisSchedulerQueue()

    with caplog.at_level("INFO"):
        extension.spider_closed(spider)

    assert "Found and deleted 2 orphan keys!" in caplog.messages


@pytest.mark.parametrize(("key_age", "expected_result"), [(None, False), (9, False), (10, False), (11, True)])
def test_is_orphan_key(monkeypatch, key_age, expected_result):
    extension = RedisSchedulerQueue()
    redis = MockRedisClient()

    def mock_object(*_args, **_kwargs):
        return key_age

    monkeypatch.setattr(MockRedisClient, "object", mock_object)
    assert extension._is_orphan_key(redis=redis, orphan_age=10, key="test-key") == expected_result
