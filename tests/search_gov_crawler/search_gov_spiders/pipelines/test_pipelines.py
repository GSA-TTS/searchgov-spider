from contextlib import suppress
from datetime import UTC, datetime

import pytest
from scrapy import Spider
from scrapy.crawler import Crawler
from scrapy.exceptions import DropItem
from scrapy.utils.reactor import install_reactor
from scrapy.utils.test import get_crawler

from search_gov_crawler.search_gov_spiders.items import (
    FreshnessSpiderException,
    FreshnessSpiderItem,
    SearchGovSpidersItem,
)
from search_gov_crawler.search_gov_spiders.pipelines.freshness_pipeline import FreshnessSpiderPipeline
from search_gov_crawler.search_gov_spiders.pipelines.pipelines import DeDeuplicatorPipeline, SearchGovSpidersPipeline


@pytest.fixture(name="intsall_reactor", autouse=True)
def fixture_install_reactor():
    install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")


@pytest.fixture(name="sample_item")
def fixture_sample_item():
    """Fixture for a valid sample item."""
    return {"url": "http://example.com"}


@pytest.fixture(name="invalid_item")
def fixture_invalid_item():
    """Fixture for an invalid item with no URL."""
    return {}


@pytest.fixture(name="sample_crawler")
def fixture_sample_crawler() -> Crawler:
    """Fixture for a mock crawlerwith a logger."""
    crawler = get_crawler(Spider)
    spider = Spider.from_crawler(crawler=crawler, name="dedup_test", allowed_domains="www.example.com")
    crawler.spider = spider
    return crawler


@pytest.fixture(name="spiders_pipeline")
def fixture_spiders_pipeline(monkeypatch, sample_crawler) -> SearchGovSpidersPipeline:
    """Fixture for SearchGovSpidersPipeline"""
    monkeypatch.setenv("SPIDER_URLS_API", "https://mockapi.com")
    return SearchGovSpidersPipeline.from_crawler(sample_crawler)


@pytest.fixture(name="deduplicator_pipeline")
def fixture_deduplicator_pipeline(sample_crawler) -> DeDeuplicatorPipeline:
    """Fixture for DeDeuplicatorPipeline with clean state."""
    return DeDeuplicatorPipeline.from_crawler(sample_crawler)


def test_spiders_pipeline_missing_url_in_item(spiders_pipeline, invalid_item):
    """
    Verify DropItem exception is raised when an item has no URL.
    """
    invalid_item["output_target"] = "csv"
    with pytest.raises(DropItem, match="Missing URL in item"):
        spiders_pipeline.process_item(invalid_item)


def test_spiders_pipeline_invalid_output_target(spiders_pipeline, sample_item):
    sample_item["output_target"] = "never-never land"
    with pytest.raises(DropItem, match="Not a valid output_target:"):
        spiders_pipeline.process_item(sample_item)


@pytest.mark.parametrize(
    ("output_target", "process_method"),
    [("csv", "_process_file_item"), ("opensearch", "_process_opensearch_item"), ("endpoint", "_process_api_item")],
)
def test_spiders_pipeline_valid_output(spiders_pipeline, mocker, output_target, process_method, sample_item):
    mock_process_item = mocker.patch(
        f"search_gov_crawler.search_gov_spiders.pipelines.pipelines.SearchGovSpidersPipeline.{process_method}",
    )
    sample_item["output_target"] = output_target
    spiders_pipeline.process_item(sample_item)
    mock_process_item.assert_called_once()


def test_spiders_pipeline_get_opensearch_client(mocker, spiders_pipeline):
    mock_opensearch = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.pipelines.SearchGovOpensearch")
    _ = spiders_pipeline.opensearch
    mock_opensearch.assert_called_once()


def test_spiders_pipeline_process_opensearch_item_no_response_bytes(spiders_pipeline, sample_item):
    with pytest.raises(DropItem, match="Missing 'response_bytes' for item"):
        spiders_pipeline._process_opensearch_item(sample_item)


@pytest.mark.parametrize(
    ("content_type", "convert_function", "valid_content_type"),
    [
        ("text/html", "convert_html", True),
        ("application/pdf", "convert_pdf", True),
        ("application/xml", "convert_html", False),
    ],
)
def test_spiders_pipeline_process_opensearch_item(
    mocker,
    spiders_pipeline,
    sample_item,
    content_type,
    convert_function,
    valid_content_type,
):
    mock_opensearch = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.pipelines.SearchGovOpensearch")
    mock_convert = mocker.patch(f"search_gov_crawler.search_gov_spiders.pipelines.pipelines.{convert_function}")
    mock_dap_visits = mocker.patch(
        "search_gov_crawler.search_gov_spiders.pipelines.pipelines.update_dap_visits_to_document"
    )

    sample_item["response_bytes"] = "you call these bytes??!?!"
    sample_item["response_language"] = "en"
    sample_item["content_type"] = content_type
    spiders_pipeline._process_opensearch_item(sample_item)  # pylint: disable=protected-access

    if valid_content_type:
        mock_convert.assert_called_once()
        mock_dap_visits.assert_called_once()
        mock_opensearch.assert_called_once()
        mock_opensearch.return_value.add_to_batch.assert_called_once()
    else:
        mock_dap_visits.assert_not_called()
        mock_opensearch.assert_not_called()


def test_spiders_pipeline_conversion_failure(caplog, mocker, spiders_pipeline, sample_item):
    mock_convert = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.pipelines.convert_html")
    mock_convert.side_effect = [Exception("This is an error!")]
    sample_item["response_bytes"] = "you call these bytes??!?!"
    sample_item["content_type"] = "text/html"

    with caplog.at_level("INFO"):
        spiders_pipeline._process_opensearch_item(sample_item)

    failed_msg = (
        "Failed to convert item "
        "{'url': 'http://example.com', 'response_bytes': 'you call these bytes??!?!', 'content_type': 'text/html'}"
    )
    no_doc_msg = (
        "No document generated for item "
        "{'url': 'http://example.com', 'response_bytes': 'you call these bytes??!?!', 'content_type': 'text/html'}"
    )
    assert failed_msg in caplog.messages
    assert no_doc_msg in caplog.messages


def test_spiders_pipeline_dap_error(caplog, mocker, spiders_pipeline, sample_item):
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.pipelines.SearchGovOpensearch")
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.pipelines.convert_html")
    mock_dap_visits = mocker.patch(
        "search_gov_crawler.search_gov_spiders.pipelines.pipelines.update_dap_visits_to_document"
    )
    mock_dap_visits.side_effect = [Exception("This is an error!")]

    sample_item["response_bytes"] = "you call these bytes??!?!"
    sample_item["content_type"] = "text/html"

    spiders_pipeline._process_opensearch_item(sample_item)
    assert any("Failed to update DAP visits for document" in message for message in caplog.messages)


def test_spiders_pipeline_opensearch_error(mocker, spiders_pipeline, sample_item):
    mock_opensearch = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.pipelines.SearchGovOpensearch")
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.pipelines.convert_html")
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.pipelines.update_dap_visits_to_document")
    mock_opensearch.side_effect = [Exception("This is an error!")]

    sample_item["response_bytes"] = "you call these bytes??!?!"
    sample_item["response_language"] = "en"
    sample_item["content_type"] = "text/html"

    with pytest.raises(DropItem, match="Failed to add item to Opensearch batch"):
        spiders_pipeline._process_opensearch_item(sample_item)


def test_spiders_pipeline_close_spider(mocker, spiders_pipeline):
    mock_opensearch = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.pipelines.SearchGovOpensearch")
    _ = spiders_pipeline.opensearch
    spiders_pipeline.close_spider()

    mock_opensearch.return_value.batch_upload.assert_called_once()


@pytest.mark.parametrize(
    "item",
    [
        {"url": "http://example.com/1"},
        {"url": "http://example.com/2"},
    ],
)
def test_deduplicator_pipeline_unique_items(deduplicator_pipeline, item):
    """
    Verify that unique items are processed successfully.
    """
    result = deduplicator_pipeline.process_item(item)
    assert result == item


def test_deduplicator_pipeline_duplicate_item(deduplicator_pipeline, sample_item):
    """
    Verify that duplicate items raise DropItem.
    """
    deduplicator_pipeline.process_item(sample_item)  # First time should pass

    with pytest.raises(DropItem, match="Item already seen!"):
        deduplicator_pipeline.process_item(sample_item)  # Duplicate raises DropItem


def test_deduplicator_pipeline_multiple_items(deduplicator_pipeline):
    """
    Verify that multiple unique items are processed without errors.
    """
    item1 = {"url": "http://example.com/1"}
    item2 = {"url": "http://example.com/2"}

    result1 = deduplicator_pipeline.process_item(item1)
    result2 = deduplicator_pipeline.process_item(item2)

    assert result1 == item1
    assert result2 == item2


def test_deduplicator_pipeline_clean_state(deduplicator_pipeline, sample_crawler):
    """
    Verify that a new instance of DeDeuplicatorPipeline starts with a clean state.
    """
    pipeline1 = deduplicator_pipeline
    pipeline2 = DeDeuplicatorPipeline.from_crawler(sample_crawler)

    item = {"url": "http://example.com/1"}

    # First pipeline processes the item
    result = pipeline1.process_item(item)
    assert result == item

    # Second pipeline should also process the same item as it has a clean state
    result = pipeline2.process_item(item)
    assert result == item


@pytest.mark.parametrize(
    ("items", "urls_seen_length"),
    [
        (
            [
                SearchGovSpidersItem(url="https://www.example.com/1"),
                SearchGovSpidersItem(url="https://www.example.com/2"),
            ],
            2,
        ),
        (
            [
                SearchGovSpidersItem(url="https://www.example.com/1"),
                SearchGovSpidersItem(url="https://www.example.com/1"),
            ],
            1,
        ),
    ],
)
def test_deduplicator_pipeline(deduplicator_pipeline, items, urls_seen_length):
    with suppress(DropItem):
        for item in items:
            deduplicator_pipeline.process_item(item)

    assert len(deduplicator_pipeline.urls_seen) == urls_seen_length


@pytest.fixture(name="freshness_spider_pipeline")
def fixture_freshness_spider_pipeline(mocker, sample_crawler) -> FreshnessSpiderPipeline:
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.freshness_pipeline.SearchGovOpensearch")
    return FreshnessSpiderPipeline.from_crawler(sample_crawler)


def test_freshness_spider_pipeline_init(freshness_spider_pipeline):
    assert isinstance(freshness_spider_pipeline, FreshnessSpiderPipeline)


def test_freshness_spider_pipeline_open_spider(freshness_spider_pipeline):
    freshness_spider_pipeline.opensearch.index_exists.return_value = False
    freshness_spider_pipeline.open_spider()
    freshness_spider_pipeline.opensearch.create_index.assert_called_once()


def test_freshness_spider_pipeline_open_spider_index_already_exists(freshness_spider_pipeline):
    freshness_spider_pipeline.opensearch.index_exists.return_value = True
    freshness_spider_pipeline.open_spider()
    freshness_spider_pipeline.opensearch.create_index.assert_not_called()


@pytest.fixture(name="freshness_spider_item")
def fixture_freshness_spider_item() -> FreshnessSpiderItem:
    return FreshnessSpiderItem(
        checked_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        result="success",
        index_name="test_index",
        id="test_id",
        path="test_path",
        domain_name="test_domain",
        marked_for_deletion=False,
        status_code="503",
        exception=FreshnessSpiderException(exception_type="TestError", exception_message="Test Exception"),
    )


def test_freshness_spider_pipeline_process_item(freshness_spider_pipeline, freshness_spider_item):
    freshness_spider_pipeline.process_item(freshness_spider_item)
    freshness_spider_pipeline.opensearch.add_to_batch.assert_called_once()


def test_freshness_spider_pipeline_process_item_exception(freshness_spider_pipeline, freshness_spider_item):
    freshness_spider_pipeline.opensearch.add_to_batch.side_effect = [Exception("This is an error!")]
    with pytest.raises(DropItem, match="Failed to add item to Opensearch batch"):
        freshness_spider_pipeline.process_item(freshness_spider_item)


def test_freshness_spider_pipeline_close_spider(freshness_spider_pipeline):
    freshness_spider_pipeline.close_spider()
    freshness_spider_pipeline.opensearch.batch_upload.assert_called_once()


def test_freshness_spider_pipeline_close_spider_exception(caplog, freshness_spider_pipeline):
    freshness_spider_pipeline.opensearch.batch_upload.side_effect = [Exception("This is an error!")]
    with caplog.at_level("INFO"):
        freshness_spider_pipeline.close_spider()

    assert "Failed to upload Opensearch batch on spider close" in caplog.messages
