from contextlib import suppress

import pytest
from scrapy import Spider
from scrapy.crawler import Crawler
from scrapy.exceptions import DropItem
from scrapy.utils.reactor import install_reactor
from scrapy.utils.test import get_crawler

from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem
from search_gov_crawler.search_gov_spiders.pipelines import DeDeuplicatorPipeline, SearchGovSpidersPipeline


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
        f"search_gov_crawler.search_gov_spiders.pipelines.SearchGovSpidersPipeline.{process_method}",
    )
    sample_item["output_target"] = output_target
    spiders_pipeline.process_item(sample_item)
    mock_process_item.assert_called_once()


def test_spiders_pipeline_get_opensearch_client(mocker, spiders_pipeline):
    mock_opensearch = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.SearchGovOpensearch")
    _ = spiders_pipeline.opensearch
    mock_opensearch.assert_called_once()


def test_spiders_pipeline_process_opensearch_item_no_response_bytes(spiders_pipeline, sample_item):
    with pytest.raises(DropItem, match="Missing 'response_bytes' for url"):
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
    mock_opensearch = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.SearchGovOpensearch")
    mock_convert = mocker.patch(f"search_gov_crawler.search_gov_spiders.pipelines.{convert_function}")
    mock_dap_visits = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.update_dap_visits_to_document")

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
    mock_convert = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.convert_html")
    mock_convert.side_effect = [Exception("This is an error!")]
    sample_item["response_bytes"] = "you call these bytes??!?!"
    sample_item["content_type"] = "text/html"

    with caplog.at_level("INFO"):
        spiders_pipeline._process_opensearch_item(sample_item)

    assert caplog.messages == [
        "Failed to convert http://example.com (type text/html)",
        "No document generated for URL http://example.com",
    ]


def test_spiders_pipeline_dap_error(caplog, mocker, spiders_pipeline, sample_item):
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.SearchGovOpensearch")
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.convert_html")
    mock_dap_visits = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.update_dap_visits_to_document")
    mock_dap_visits.side_effect = [Exception("This is an error!")]

    sample_item["response_bytes"] = "you call these bytes??!?!"
    sample_item["content_type"] = "text/html"

    spiders_pipeline._process_opensearch_item(sample_item)
    assert "Failed to update DAP visits for url: http://example.com, content_type: text/html" in caplog.messages


def test_spiders_pipeline_opensearch_error(mocker, spiders_pipeline, sample_item):
    mock_opensearch = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.SearchGovOpensearch")
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.convert_html")
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.update_dap_visits_to_document")
    mock_opensearch.side_effect = [Exception("This is an error!")]

    sample_item["response_bytes"] = "you call these bytes??!?!"
    sample_item["response_language"] = "en"
    sample_item["content_type"] = "text/html"

    with pytest.raises(DropItem, match="Failed to add item to Opensearch batch"):
        spiders_pipeline._process_opensearch_item(sample_item)


def test_spiders_pipeline_close_spider(mocker, spiders_pipeline):
    mock_opensearch = mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.SearchGovOpensearch")
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


def test_deduplicator_pipeline_clean_state(sample_crawler):
    """
    Verify that a new instance of DeDeuplicatorPipeline starts with a clean state.
    """
    pipeline1 = DeDeuplicatorPipeline.from_crawler(sample_crawler)
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
def test_deduplicator_pipeline(sample_crawler, items, urls_seen_length):
    pl = DeDeuplicatorPipeline.from_crawler(sample_crawler)

    with suppress(DropItem):
        for item in items:
            pl.process_item(item)

    assert len(pl.urls_seen) == urls_seen_length


def test_item_repr():
    item = SearchGovSpidersItem(
        url="https://www.example.com",
        output_target="csv",
        content_type="text/html",
        response_language="en",
        response_bytes=b"long long long long long long long long long response bytes",
    )

    assert str(item) == (
        "Item(url=https://www.example.com, output_target=csv, content_type=text/html, response_language=en)"
    )
