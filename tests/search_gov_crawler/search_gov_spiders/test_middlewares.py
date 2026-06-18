import operator

import pytest
from scrapy import Request, Spider
from scrapy.exceptions import IgnoreRequest
from scrapy.http.response import Response
from scrapy.utils.reactor import install_reactor
from scrapy.utils.test import get_crawler

from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem
from search_gov_crawler.search_gov_spiders.middlewares import (
    FreshnessSpiderDownloaderMiddleware,
    SearchGovSpidersDownloaderMiddleware,
    SearchGovSpidersOffsiteMiddleware,
    SearchGovSpidersSpiderMiddleware,
)


@pytest.fixture(name="intsall_reactor", autouse=True)
def fixture_install_reactor():
    install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")


@pytest.fixture(name="test_crawler")
def fixture_test_crawler():
    return get_crawler(Spider)


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
def test_offsite_process_request_domain_filtering(test_crawler, allowed_domain, allowed_domain_path, url, allowed):
    spider = Spider.from_crawler(
        crawler=test_crawler,
        name="offsite_test",
        allowed_domains=allowed_domain,
        allowed_domain_paths=allowed_domain_path,
    )
    test_crawler.spider = spider
    mw = SearchGovSpidersOffsiteMiddleware.from_crawler(test_crawler)
    mw.spider_opened(spider)
    request = Request(url)
    if allowed:
        assert mw.process_request(request) is None
    else:
        with pytest.raises(IgnoreRequest):
            mw.process_request(request)


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
def test_offsite_invalid_domain_paths(test_crawler, allowed_domain, allowed_domain_path, warning_message):
    test_crawler.spider = Spider.from_crawler(
        crawler=test_crawler,
        name="offsite_test",
        allowed_domains=allowed_domain,
        allowed_domain_paths=allowed_domain_path,
    )
    mw = SearchGovSpidersOffsiteMiddleware.from_crawler(test_crawler)

    with pytest.warns(UserWarning, match=warning_message):
        mw.spider_opened(test_crawler.spider)

    request = Request("http://www.example.com")
    assert mw.process_request(request) is None


def test_offsite_invalid_domain_in_starting_urls(test_crawler, caplog):
    test_crawler.spider = Spider.from_crawler(
        crawler=test_crawler,
        name="offsite_test",
        allowed_domains=["example.com"],
        start_urls=["http://www.not-an-example.com"],
    )
    mw = SearchGovSpidersOffsiteMiddleware.from_crawler(test_crawler)
    mw.spider_opened(test_crawler.spider)

    request = Request("http://www.not-an-example.com")
    with pytest.raises(IgnoreRequest), caplog.at_level("ERROR"):
        mw.process_request(request=request)

    msg = (
        "IgnoreRequest raised for starting URL due to Offsite request: "
        f"{request.url}, allowed_domains: {test_crawler.spider.allowed_domains}"
    )
    assert msg in caplog.messages


@pytest.fixture(name="downloader_middleware")
def test_spider_downloader_middleware(test_crawler):
    test_crawler.spider = Spider.from_crawler(
        crawler=test_crawler,
        name="test",
        allow_query_string=False,
        allowed_domains="example.com",
    )
    mw = SearchGovSpidersDownloaderMiddleware()
    request = Request("http://www.example.com/test")
    return (mw, request)


def test_downloader_middleware_process_response(downloader_middleware):
    mw, request = downloader_middleware
    response = Response("http://www.example.com/test")
    assert mw.process_response(request, response) == response


def test_downloader_middleware_process_request(downloader_middleware):
    mw, request = downloader_middleware
    assert mw.process_request(request) is None


def test_downloader_middleware_process_exception(downloader_middleware):
    mw, request = downloader_middleware
    exception = Exception("This is just a test!")
    assert mw.process_exception(request, exception) is None


@pytest.mark.parametrize(
    ("dont_filter", "allow_query_string", "none_test"),
    [(True, True, "is_not"), (True, False, "is_not"), (False, True, "is_not"), (False, False, "is_")],
)
def test_spider_middleware_allow_query_string_request(test_crawler, dont_filter, allow_query_string, none_test):
    test_crawler.spider = Spider.from_crawler(
        crawler=test_crawler,
        name="test",
        allow_query_string=allow_query_string,
        allowed_domains="example.com",
    )
    mw = SearchGovSpidersSpiderMiddleware.from_crawler(test_crawler)
    request = Request("http://www.example.com/test?parm=value", dont_filter=dont_filter)

    assert getattr(operator, none_test)(mw.get_processed_request(request=request, response=None), None)


@pytest.mark.parametrize(
    ("url_in", "url_out"),
    [
        ("https://www.example.com/test", "https://www.example.com/test"),
        ("http://www.example.com/test;jsessionid=12345", "http://www.example.com/test"),
        ("http://www.example.com/test;JSESSIONID=12345", "http://www.example.com/test"),
        (
            "https://www.example.com/test/1/more;jsessionid=67890",
            "https://www.example.com/test/1/more",
        ),
        ("http://www.example.com/test;jsessionid=12345?query=string", "http://www.example.com/test?query=string"),
    ],
)
def test_spider_middleware_jsessionid_removal_request(test_crawler, url_in, url_out):
    test_crawler.spider = Spider.from_crawler(
        crawler=test_crawler,
        name="test",
        allow_query_string=True,
        allowed_domains="example.com",
    )
    mw = SearchGovSpidersSpiderMiddleware.from_crawler(test_crawler)
    request = Request(url_in)
    processed_request = mw.get_processed_request(request=request, response=None)
    assert processed_request.url == url_out


@pytest.mark.parametrize(
    ("dont_filter", "allow_query_string", "none_test"),
    [(True, True, "is_not"), (True, False, "is_not"), (False, True, "is_not"), (False, False, "is_")],
)
def test_spider_middleware_allow_query_string_item(test_crawler, dont_filter, allow_query_string, none_test):
    test_crawler.spider = Spider.from_crawler(
        crawler=test_crawler,
        name="test",
        allow_query_string=allow_query_string,
        allowed_domains="example.com",
    )
    mw = SearchGovSpidersSpiderMiddleware.from_crawler(test_crawler)
    item = SearchGovSpidersItem(url="http://www.example.com/test?parm=value")
    response = Response(
        url="http://www.example.com/test?parm=value",
        status=200,
        request=Request("http://www.example.com/test?parm=value", dont_filter=dont_filter),
    )

    assert getattr(operator, none_test)(mw.get_processed_item(item, response), None)


@pytest.mark.parametrize(
    ("url_in", "url_out"),
    [
        ("https://www.example.com/test", "https://www.example.com/test"),
        ("http://www.example.com/test;jsessionid=12345", "http://www.example.com/test"),
        ("http://www.example.com/test;JSESSIONID=12345", "http://www.example.com/test"),
        (
            "https://www.example.com/test/1/more;jsessionid=67890",
            "https://www.example.com/test/1/more",
        ),
        ("http://www.example.com/test;jsessionid=12345?query=string", "http://www.example.com/test?query=string"),
    ],
)
def test_spider_middleware_jsessionid_removal_item(test_crawler, url_in, url_out):
    test_crawler.spider = Spider.from_crawler(
        crawler=test_crawler,
        name="test",
        allow_query_string=True,
        allowed_domains="example.com",
    )
    mw = SearchGovSpidersSpiderMiddleware.from_crawler(test_crawler)
    item = SearchGovSpidersItem(url=url_in)
    response = Response(url=url_in, status=200, request=Request(url_in))

    assert mw.get_processed_item(item, response).get("url") == url_out


def test_spider_middleware_process_spider_input(test_crawler):
    test_crawler.spider = Spider.from_crawler(
        crawler=test_crawler,
        name="test",
        allowed_domains="example.com",
        start_urls=["http://www.example.com"],
    )
    mw = SearchGovSpidersSpiderMiddleware.from_crawler(test_crawler)

    assert mw.process_spider_input(response=Response(url="example.com", status=200)) is None


def testspider_middleware_process_spider_output(test_crawler):
    sample_result = ["1", "2", "3"]
    test_crawler.spider = Spider.from_crawler(
        crawler=test_crawler,
        name="test",
        allowed_domains="example.com",
        start_urls=["http://www.example.com"],
    )
    mw = SearchGovSpidersSpiderMiddleware.from_crawler(test_crawler)
    assert (
        list(mw.process_spider_output(response=Response(url="example.com", status=200), result=sample_result))
        == sample_result
    )


def test_spider_middleware_spider_exception_start_url(caplog, test_crawler):
    spider = Spider.from_crawler(
        crawler=test_crawler,
        name="test",
        allow_query_string=True,
        allowed_domains="example.com",
        start_urls=["http://www.example.com"],
    )
    test_crawler.spider = spider
    mw = SearchGovSpidersSpiderMiddleware.from_crawler(test_crawler)

    mw.spider_opened(spider)
    response = Response(
        url="http://www.example.com",
        status=403,
        request=Request("http://www.example.com", meta={"is_start_request": True}),
    )

    with caplog.at_level("ERROR"):
        mw.process_spider_exception(
            response=response,
            exception=IgnoreRequest("Ignore this test request"),
        )
        msg = (
            "Error occured while accessing start url: http://www.example.com: "
            "response: <403 http://www.example.com>, Ignore this test request"
        )
        assert msg in caplog.messages


def test_freshness_spider_downloader_middleware(caplog, test_crawler):
    test_crawler.spider = Spider.from_crawler(name="test", crawler=test_crawler)

    with caplog.at_level("INFO"):
        mw = FreshnessSpiderDownloaderMiddleware.from_crawler(test_crawler)
    mw_kwargs = {"request": Request("http://www.example.com"), "exception": Exception("This is just a test!")}
    result = mw.process_exception(**mw_kwargs)
    expected_result = Response(url="http://www.example.com", status=0, request=mw_kwargs["request"])
    expected_result.meta["exception"] = mw_kwargs["exception"]

    assert isinstance(result, Response)
    assert result.url == "http://www.example.com"
    assert result.status == 0
    assert result.request == mw_kwargs["request"]
    assert result.meta["exception"] == mw_kwargs["exception"]
    assert "Error occured while accessing URL: http://www.example.com: This is just a test!" in caplog.messages
