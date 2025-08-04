import re

import pytest
from scrapy import Request, Spider
from scrapy.exceptions import IgnoreRequest
from scrapy.http.response import Response
from scrapy.utils.reactor import install_reactor
from scrapy.utils.test import get_crawler

from search_gov_crawler.search_gov_spiders.middlewares import (
    SearchGovSpidersDownloaderMiddleware,
    SearchGovSpidersOffsiteMiddleware,
    SearchGovSpidersSpiderMiddleware,
)


@pytest.fixture(name="intsall_reactor", autouse=True)
def fixture_install_reactor():
    install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")


MIDDLEWARE_TEST_CASES = [
    (["example.com"], ["example.com"], "http://www.example.com/1", True),
    (["sub.example.com"], ["sub.example.com"], "http://sub.example.com/1", True),
    (["sub.example.com"], ["sub.example.com"], "http://www.example.com/1", False),
    (["example.com"], ["example.com/path"], "http://example.com/1", False),
    (["sub.example.com"], ["sub.example.com/path/"], "http://sub.example.com/path/more/more", True),
    (["sub.example.com"], ["sub.example.com/path/"], "http://sub.example.com/path/1", True),
    (["example.com"], None, "http://www.example.com/2", True),
    (["example.com"], [None], "http://www.example.com/2", True),
]


@pytest.mark.parametrize(("allowed_domain", "allowed_domain_path", "url", "allowed"), MIDDLEWARE_TEST_CASES)
def test_offsite_process_request_domain_filtering(allowed_domain, allowed_domain_path, url, allowed):
    crawler = get_crawler(Spider)
    spider = Spider.from_crawler(
        crawler=crawler,
        name="offsite_test",
        allowed_domains=allowed_domain,
        allowed_domain_paths=allowed_domain_path,
    )
    mw = SearchGovSpidersOffsiteMiddleware.from_crawler(crawler)
    mw.spider_opened(spider)
    request = Request(url)
    if allowed:
        assert mw.process_request(request, spider) is None
    else:
        with pytest.raises(IgnoreRequest):
            mw.process_request(request, spider)


INVALID_DOMAIN_TEST_CASES = [
    (
        ["example.com"],
        ["http://www.example.com"],
        (
            "allowed_domain_paths accepts only domains, not URLs. "
            "Ignoring URL entry http://www.example.com in allowed_domain_paths."
        ),
    ),
    (
        ["example.com"],
        ["example.com:443"],
        (
            "allowed_domain_paths accepts only domains without ports. "
            "Ignoring entry example.com:443 in allowed_domain_paths."
        ),
    ),
]


@pytest.mark.parametrize(("allowed_domain", "allowed_domain_path", "warning_message"), INVALID_DOMAIN_TEST_CASES)
def test_offsite_invalid_domain_paths(allowed_domain, allowed_domain_path, warning_message):
    crawler = get_crawler(Spider)
    spider = Spider.from_crawler(
        crawler=crawler,
        name="offsite_test",
        allowed_domains=allowed_domain,
        allowed_domain_paths=allowed_domain_path,
    )
    mw = SearchGovSpidersOffsiteMiddleware.from_crawler(crawler)

    with pytest.warns(UserWarning, match=warning_message):
        mw.spider_opened(spider)

    request = Request("http://www.example.com")
    assert mw.process_request(request, spider) is None


def test_offsite_invalid_domain_in_starting_urls(caplog):
    crawler = get_crawler(Spider)
    spider = Spider.from_crawler(
        crawler=crawler,
        name="offsite_test",
        allowed_domains=["example.com"],
        start_urls=["http://www.not-an-example.com"],
    )
    mw = SearchGovSpidersOffsiteMiddleware.from_crawler(crawler)
    mw.spider_opened(spider)

    request = Request("http://www.not-an-example.com")
    with pytest.raises(IgnoreRequest), caplog.at_level("ERROR"):
        mw.process_request(request=request, spider=spider)

    msg = (
        "IgnoreRequest raised for starting URL due to Offsite request: "
        f"{request.url}, allowed_domains: {spider.allowed_domains}"
    )
    assert msg in caplog.messages


def test_spider_downloader_middleware():
    crawler = get_crawler(Spider)
    spider = Spider.from_crawler(crawler=crawler, name="test", allow_query_string=False, allowed_domains="example.com")
    mw = SearchGovSpidersDownloaderMiddleware.from_crawler(crawler)

    mw.spider_opened(spider)
    request = Request("http://www.example.com/test?parm=value")

    with pytest.raises(IgnoreRequest):
        mw.process_request(request=request, spider=spider)


@pytest.mark.parametrize("allow_query_string", [True, False])
def test_spider_downloader_middleware_allow_query_string(allow_query_string):
    crawler = get_crawler(Spider)
    spider = Spider.from_crawler(
        crawler=crawler,
        name="test",
        allow_query_string=allow_query_string,
        allowed_domains="example.com",
    )
    mw = SearchGovSpidersDownloaderMiddleware.from_crawler(crawler)

    mw.spider_opened(spider)

    request = Request("http://www.example.com/test?parm=value")
    error_msg = f"Ignoring request with query string: {request.url}"
    if allow_query_string:
        assert mw.process_request(request=request, spider=spider) is None
    else:
        with pytest.raises(IgnoreRequest, match=re.escape(error_msg)):
            mw.process_request(request=request, spider=spider)


def test_spider_middleware_spider_exception_start_url(caplog):
    crawler = get_crawler(Spider)
    spider = Spider.from_crawler(
        crawler=crawler,
        name="test",
        allow_query_string=True,
        allowed_domains="example.com",
        start_urls=["http://www.example.com"],
    )
    mw = SearchGovSpidersSpiderMiddleware.from_crawler(crawler)

    mw.spider_opened(spider)
    response = Response(
        url="http://www.example.com",
        status=403,
        request=Request("http://www.example.com", meta={"is_start_request": True}),
    )

    with caplog.at_level("ERROR"):
        mw.process_spider_exception(
            response=response,
            exception=IgnoreRequest("Igore this test request"),
            spider=spider,
        )
        msg = (
            "Error occured while accessing start url: http://www.example.com: "
            "response: <403 http://www.example.com>, Igore this test request"
        )
        assert msg in caplog.messages
