import os
from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest
from scrapy import Spider
from scrapy.crawler import Crawler
from scrapy.exceptions import DropItem
from scrapy.utils.reactor import install_reactor
from scrapy.utils.test import get_crawler

from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem
from search_gov_crawler.search_gov_spiders.pipelines import (
    DeDeuplicatorPipeline,
    SearchGovSpidersPipeline,
)


# ---------------------------
# Fixtures
# ---------------------------
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
    return get_crawler(Spider)

@pytest.fixture(name="pipeline_no_api")
def fixture_pipeline_no_api(sample_crawler) -> SearchGovSpidersPipeline:
    """Fixture for SearchGovSpidersPipeline with no SPIDER_URLS_API."""
    with patch.dict(os.environ, {}, clear=True):
        return SearchGovSpidersPipeline.from_crawler(sample_crawler)


@pytest.fixture(name="deduplicator_pipeline")
def fixture_deduplicator_pipeline(sample_crawler) -> DeDeuplicatorPipeline:
    """Fixture for DeDeuplicatorPipeline with clean state."""
    return DeDeuplicatorPipeline.from_crawler(sample_crawler)

# ---------------------------
# Tests for SearchGovSpidersPipeline
# ---------------------------

def test_missing_url_in_item(pipeline_no_api, invalid_item):
    """
    Verify DropItem exception is raised when an item has no URL.
    """
    invalid_item["output_target"] = "csv"
    with pytest.raises(DropItem, match="Missing URL in item"):
        pipeline_no_api.process_item(invalid_item)

# ---------------------------
# Tests for DeDeuplicatorPipeline
# ---------------------------

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
