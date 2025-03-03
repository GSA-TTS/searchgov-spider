import re

import pytest
from scrapy.http.request import Request
from scrapy.http.response import Response

from search_gov_crawler.search_gov_spiders.spiders.domain_spider import DomainSpider
from search_gov_crawler.search_gov_spiders.spiders.domain_spider_js import DomainSpiderJs

TEST_URL = "http://example.com"


@pytest.fixture(name="spider", params=[DomainSpider(output_target="csv"), DomainSpiderJs(output_target="csv")])
def fixture_spider(request):
    return request.param


def get_results(spider, content: str):
    request = Request(url=TEST_URL, encoding="utf-8")

    response = Response(url=TEST_URL, request=request, headers={"content-type": content})

    spider.output_target = "csv"
    spider.allowed_domains = ["example.com"]
    return next(spider.parse_item(response), None)


def test_valid_content(spider):
    results = get_results(spider, "text/html")
    assert results is not None and results.get("url") == TEST_URL


def test_valid_content_plus(spider):
    results = get_results(spider, "text/html;utf-8")
    assert results is not None and results.get("url") == TEST_URL


def test_invalid_content(spider):
    results = get_results(spider, "media/image")
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
