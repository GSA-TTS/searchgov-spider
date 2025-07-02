import re

import pytest
from scrapy.http.request import Request
from scrapy.http.response import Response

import search_gov_crawler.search_gov_spiders.helpers.domain_spider as helpers
from search_gov_crawler.search_gov_spiders.spiders.domain_spider import DomainSpider
from search_gov_crawler.search_gov_spiders.spiders.domain_spider_js import DomainSpiderJs

TEST_URL = "http://example.com"


@pytest.fixture(name="spider_args")
def fixture_spider_args() -> dict:
    return {
        "allowed_domains": "example.com",
        "start_urls": "http://example.com/",
        "output_target": "csv",
        "allow_query_string": True,
        "deny_paths": "/deny/path",
        "prevent_follow": False,
    }


@pytest.fixture(name="domain_spider")
def fixture_domain_spider(monkeypatch, spider_args) -> DomainSpider:
    monkeypatch.setattr(helpers, "get_domain_visits", lambda _: {})
    return DomainSpider(**spider_args)


@pytest.fixture(name="domain_spider_js")
def fixture_domain_spider_js(monkeypatch, spider_args) -> DomainSpiderJs:
    monkeypatch.setattr(helpers, "get_domain_visits", lambda _: {})
    return DomainSpiderJs(**spider_args)


@pytest.mark.parametrize(
    ("spider_fixture", "content_type"),
    [
        ("domain_spider", "text/html"),
        ("domain_spider_js", "text/html"),
        ("domain_spider", "text/html;utf-8"),
        ("domain_spider_js", "text/html;utf-8"),
    ],
)
def test_valid_content(request, spider_fixture, content_type):
    spider = request.getfixturevalue(spider_fixture)
    request = Request(url=TEST_URL, encoding="utf-8")
    response = Response(url=TEST_URL, request=request, headers={"content-type": content_type})
    results = next(spider.parse_item(response), None)
    assert results is not None
    assert results.get("url") == TEST_URL


@pytest.mark.parametrize(
    ("spider_fixture", "content_type"),
    [
        ("domain_spider", "media/image"),
        ("domain_spider_js", "media/image"),
    ],
)
def test_invalid_content(request, spider_fixture, content_type):
    spider = request.getfixturevalue(spider_fixture)
    request = Request(url=TEST_URL, encoding="utf-8")
    response = Response(url=TEST_URL, request=request, headers={"content-type": content_type})
    results = next(spider.parse_item(response), None)
    assert results is None


INVALID_ARGS_TEST_CASES = [
    (
        DomainSpider,
        {"allowed_domains": "test.example.com", "output_target": "csv"},
        "Invalid arguments: allowed_domains and start_urls must be used together or not at all.",
    ),
    (
        DomainSpiderJs,
        {"allowed_domains": "test.example.com", "output_target": "csv"},
        "Invalid arguments: allowed_domains and start_urls must be used together or not at all.",
    ),
    (
        DomainSpider,
        {"allowed_domains": "test.example.com", "start_urls": "http://test.example.com/", "output_target": "yaml"},
        "Invalid arguments: output_target must be one of the following: ['csv', 'endpoint', 'elasticsearch']",
    ),
    (
        DomainSpiderJs,
        {"allowed_domains": "test.example.com", "start_urls": "http://test.example.com/", "output_target": "yaml"},
        "Invalid arguments: output_target must be one of the following: ['csv', 'endpoint', 'elasticsearch']",
    ),
    (
        DomainSpider,
        {"output_target": "yaml"},
        "Invalid arguments: output_target must be one of the following: ['csv', 'endpoint', 'elasticsearch']",
    ),
    (
        DomainSpiderJs,
        {"output_target": "yaml"},
        "Invalid arguments: output_target must be one of the following: ['csv', 'endpoint', 'elasticsearch']",
    ),
]


@pytest.mark.parametrize(("spider_cls", "kwargs", "msg"), INVALID_ARGS_TEST_CASES)
def test_invalid_args(spider_cls, kwargs, msg):
    with pytest.raises(ValueError, match=re.escape(msg)):
        spider_cls(**kwargs)


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("allowed_domains", ["example.com"]),
        ("start_urls", ["http://example.com/"]),
        ("output_target", "csv"),
        ("allow_query_string", True),
        ("_deny_paths", "/deny/path"),
    ],
)
def test_domain_spider_init(domain_spider, attribute, value):
    assert getattr(domain_spider, attribute) == value


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("allowed_domains", ["example.com"]),
        ("start_urls", ["http://example.com/"]),
        ("output_target", "csv"),
        ("allow_query_string", True),
        ("_deny_paths", "/deny/path"),
    ],
)
def test_domain_spider_js_init(domain_spider_js, attribute, value):
    assert getattr(domain_spider_js, attribute) == value


@pytest.mark.parametrize(
    ("spider_cls", "allow_query_string"),
    [
        (DomainSpider, "False"),
        (DomainSpider, "something else"),
        (DomainSpiderJs, "false"),
        (DomainSpiderJs, "not a boolean"),
    ],
)
def test_spider_init_allow_query_string_str_input(monkeypatch, spider_cls, spider_args, allow_query_string):
    monkeypatch.setattr(helpers, "get_domain_visits", lambda _: {})
    spider_args["allow_query_string"] = allow_query_string
    spider = spider_cls(**spider_args)
    assert spider.allow_query_string is False
