from datetime import UTC, datetime

import pytest
from freezegun import freeze_time
from scrapy import Request
from scrapy.exceptions import DontCloseSpider
from scrapy.http.response import Response

from search_gov_crawler.search_gov_spiders.items import (
    FreshnessSpiderExceptionItem,
    FreshnessSpiderMarkedForDeletionItem,
    FreshnessSpiderNotMarkedForDeletionItem,
)
from search_gov_crawler.search_gov_spiders.spiders.freshness_spider import FreshnessSpider


@pytest.fixture(name="freshness_spider")
def fixture_freshness_spider(mocker):
    mock_opensearch = mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.SearchGovOpensearch")
    mock_opensearch.return_value.index_name = "test_index"

    freshness_spider = FreshnessSpider(query='{"test": "query"}', max_results="100")
    freshness_spider.crawler = mocker.MagicMock()

    return freshness_spider


def test_freshness_spider_args(freshness_spider):
    assert freshness_spider.query == {"test": "query"}
    assert freshness_spider.max_results == 100


FRESHNESS_SPIDER_RESPONSE_PARSE_TEST_CASES = [
    (
        Response(url="http://example.com", status=301, request=Request(url="http://example.com")),
        FreshnessSpiderMarkedForDeletionItem,
    ),
    (
        Response(url="http://example.com", status=302, request=Request(url="http://example.com")),
        FreshnessSpiderMarkedForDeletionItem,
    ),
    (
        Response(url="http://example.com", status=403, request=Request(url="http://example.com")),
        FreshnessSpiderNotMarkedForDeletionItem,
    ),
    (
        Response(url="http://example.com", status=404, request=Request(url="http://example.com")),
        FreshnessSpiderMarkedForDeletionItem,
    ),
    (
        Response(url="http://example.com", status=500, request=Request(url="http://example.com")),
        FreshnessSpiderNotMarkedForDeletionItem,
    ),
]


@freeze_time("2026-01-01 00:00:00", tz_offset=0)
@pytest.mark.parametrize(("response", "expected_item_cls"), FRESHNESS_SPIDER_RESPONSE_PARSE_TEST_CASES)
def test_freshness_spider_response_parse(freshness_spider, response, expected_item_cls):
    response.meta["document_id"] = "test_id"
    response.meta["domain_name"] = "test_domain"

    item = next(freshness_spider.parse(response))
    assert isinstance(item, expected_item_cls)
    assert item.to_dict() == {
        "checked_at": datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        "result": str(response.status),
        "status_code": str(response.status),
        "index_name": "test_index",
        "id": "test_id",
        "path": response.url,
        "domain_name": "test_domain",
        "exception": None,
        "marked_for_deletion": expected_item_cls == FreshnessSpiderMarkedForDeletionItem,
    }


@freeze_time("2026-01-01 00:00:00", tz_offset=0)
def test_freshness_spider_exception_parse(freshness_spider):
    response = Response(url="http://example.com", status=0, request=Request(url="http://example.com"))
    response.meta["document_id"] = "test_id"
    response.meta["domain_name"] = "test_domain"
    response.meta["exception"] = ValueError("This is an error!")

    item = next(freshness_spider.parse(response))
    assert isinstance(item, FreshnessSpiderExceptionItem)
    assert item.to_dict() == {
        "checked_at": datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        "result": "ValueError",
        "status_code": None,
        "index_name": "test_index",
        "id": "test_id",
        "path": response.url,
        "domain_name": "test_domain",
        "marked_for_deletion": False,
        "exception": {
            "exception_type": "ValueError",
            "exception_message": "This is an error!",
        },
    }


def test_freshness_spider_ignore_parse(caplog, freshness_spider):
    response = Response(url="http://example.com", status=200, request=Request(url="http://example.com"))
    with caplog.at_level("DEBUG"):
        item = next(freshness_spider.parse(response), None)

    assert item is None
    assert "Ignoring 200 response from http://example.com since it does not indicate a failure." in caplog.messages


@pytest.mark.asyncio
async def test_freshness_spider_start_no_docs(mocker, caplog, freshness_spider):
    mock_count = mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.count_matching_documents")
    mock_count.return_value = 0

    with caplog.at_level("INFO"):
        _ = {value async for value in freshness_spider.start()}

    assert "No documents found matching query" in caplog.messages


@pytest.fixture(name="matching_documents")
def fixture_matching_documents():
    return [
        {"_id": "1", "_source": {"path": "http://example1.com", "domain_name": "example1.com"}},
        {"_id": "2", "_source": {"path": "http://example2.com", "domain_name": "example2.com"}},
        {"_id": "3", "_source": {"path": "http://example3.com", "domain_name": "example3.com"}},
        {"_id": "4", "_source": {"path": "http://example4.com", "domain_name": "example4.com"}},
        {"_id": "5", "_source": {"path": "http://example5.com", "domain_name": "example5.com"}},
    ]


@pytest.mark.asyncio
async def test_freshness_spider_start(mocker, matching_documents, freshness_spider):
    mock_count = mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.count_matching_documents")
    mock_count.return_value = 5

    def yield_docs(*_args, **_kwargs):
        yield from matching_documents

    mock_docs = mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.get_matching_documents")
    mock_docs.side_effect = yield_docs

    results = [request async for request in freshness_spider.start()]
    assert len(results) == 5
    for idx, result in enumerate(results, start=1):
        assert isinstance(result, Request)
        assert result.url == f"http://example{idx}.com"
        assert result.method == "HEAD"
        assert result.meta["document_id"] == str(idx)
        assert result.meta["domain_name"] == f"example{idx}.com"


@pytest.mark.asyncio
async def test_freshness_spider_start_max_results(mocker, matching_documents):
    mock_count = mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.count_matching_documents")
    mock_count.return_value = 5

    def yield_docs(*_args, **_kwargs):
        yield from matching_documents

    mock_docs = mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.get_matching_documents")
    mock_docs.side_effect = yield_docs

    mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.SearchGovOpensearch")
    freshness_spider = FreshnessSpider(query='{"test": "query"}', max_results="2")

    results = [request async for request in freshness_spider.start()]
    assert len(results) == 2


FRESHNESS_SPIDER_START_INVALID_DOCS = [
    {"_source": {"path": "http://example1.com", "domain_name": "example1.com"}},
    {"_id": "1"},
    {"_id": "1", "_source": {"domain_name": "example1.com"}},
    {"_id": "1", "_source": {"path": "http://example1.com"}},
]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_doc", FRESHNESS_SPIDER_START_INVALID_DOCS)
async def test_freshness_spider_start_invalid_doc(mocker, freshness_spider, invalid_doc):
    mock_count = mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.count_matching_documents")
    mock_count.return_value = 1

    def yield_docs(*_args, **_kwargs):
        yield from [invalid_doc]

    mock_docs = mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.get_matching_documents")
    mock_docs.side_effect = yield_docs

    with pytest.raises(ValueError, match="Invalid Document:"):
        _ = {value async for value in freshness_spider.start()}


@pytest.mark.parametrize(
    ("max_results", "doc_batch_size", "expected_results"),
    [(10, 100, 3), (2, 10, 2), (10, 1, 1)],
)
def test_next_batch(mocker, freshness_spider, max_results, doc_batch_size, expected_results):
    def yield_docs(*_args, **_kwargs):
        yield from [
            {"_id": "123", "_source": {"path": "http://example1.com", "domain_name": "example1.com"}},
            {"_id": "456", "_source": {"path": "http://example2.com", "domain_name": "example2.com"}},
            {"_id": "789", "_source": {"path": "http://example3.com", "domain_name": "example3.com"}},
        ]

    mocker.patch.object(freshness_spider, "source_documents", yield_docs())
    freshness_spider.max_results = max_results
    freshness_spider.doc_batch_size = doc_batch_size

    assert len(list(freshness_spider._next_batch())) == expected_results


def test_next_batch_no_source_documents(freshness_spider):
    assert list(freshness_spider._next_batch()) == []


def test_crawl_next_batch(mocker, freshness_spider):
    freshness_spider.source_documents = True

    def yield_requests(*_args, **_kwargs):
        yield from [Request(url="https://1.example.com"), Request(url="https://2.example.com")]

    mock_next_batch = mocker.patch(
        "search_gov_crawler.search_gov_spiders.spiders.freshness_spider.FreshnessSpider._next_batch"
    )
    mock_next_batch.side_effect = yield_requests

    with pytest.raises(DontCloseSpider):
        freshness_spider.crawl_next_batch()
    assert freshness_spider.crawler.engine.crawl.call_count == 2


def test_crawl_next_batch_no_source_documents(freshness_spider):
    freshness_spider.crawl_next_batch()
    freshness_spider.crawler.engine.crawl.assert_not_called()


@pytest.fixture(name="freshness_spider_settings")
def fixture_freshness_spider_settings(project_settings):
    FreshnessSpider.update_settings(settings=project_settings)
    return project_settings


PROJECT_SETTINGS_TEST_CASES = [
    ("CONCURRENT_REQUESTS", 5),
    ("CONCURRENT_REQUESTS_PER_DOMAIN", 5),
    ("DOWNLOAD_DELAY", 0.25),
    ("DOWNLOADER_MIDDLEWARES", {"search_gov_spiders.middlewares.FreshnessSpiderDownloaderMiddleware": 100}),
    ("EXTENSIONS", {"search_gov_spiders.extensions.json_logging.JsonLogging": -1}),
    ("ITEM_PIPELINES", {"search_gov_spiders.pipelines.freshness_pipeline.FreshnessSpiderPipeline": 100}),
    ("HTTPERROR_ALLOW_ALL", True),
    ("REDIRECT_ENABLED", False),
    ("ROBOTSTXT_OBEY", False),
]


@pytest.mark.parametrize(("setting", "value"), PROJECT_SETTINGS_TEST_CASES)
def test_freshness_spider_update_settings(freshness_spider_settings, setting, value):
    assert freshness_spider_settings.get(setting) == value


def test_freshness_spider_from_crawler(mocker):
    mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.SearchGovOpensearch")
    freshness_spider = FreshnessSpider.from_crawler(
        crawler=mocker.MagicMock(), query='{"test": "query"}', max_results="100"
    )

    # assert call_count == 2 instead of 1 because close_spider is also being connected
    assert freshness_spider.crawler.signals.connect.call_count == 2
