import os
from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest
from scrapy.exceptions import DropItem

from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem
from search_gov_crawler.search_gov_spiders.pipelines import (
    DeDeuplicatorPipeline,
    SearchGovSpidersPipeline,
)

# ---------------------------
# Fixtures
# ---------------------------


@pytest.fixture
def sample_item():
    """Fixture for a valid sample item."""
    return {"url": "http://example.com"}


@pytest.fixture
def invalid_item():
    """Fixture for an invalid item with no URL."""
    return {}


@pytest.fixture
def sample_spider():
    """Fixture for a mock spider with a logger."""

    class SpiderMock:
        logger = MagicMock()

    return SpiderMock()


@pytest.fixture
def pipeline_no_api():
    """Fixture for SearchGovSpidersPipeline with no SPIDER_URLS_API."""
    with patch.dict(os.environ, {}, clear=True):
        return SearchGovSpidersPipeline()


@pytest.fixture
def deduplicator_pipeline():
    """Fixture for DeDeuplicatorPipeline with clean state."""
    return DeDeuplicatorPipeline()


# ---------------------------
# Tests for SearchGovSpidersPipeline
# ---------------------------


def test_missing_url_in_item(pipeline_no_api, sample_spider, invalid_item):
    """
    Verify DropItem exception is raised when an item has no URL.
    """
    invalid_item["output_target"] = "csv"
    with pytest.raises(DropItem, match="Missing URL in item"):
        pipeline_no_api.process_item(invalid_item, sample_spider)


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
    result = deduplicator_pipeline.process_item(item, None)
    assert result == item


def test_deduplicator_pipeline_duplicate_item(deduplicator_pipeline, sample_item):
    """
    Verify that duplicate items raise DropItem.
    """
    deduplicator_pipeline.process_item(sample_item, None)  # First time should pass

    with pytest.raises(DropItem, match="Item already seen!"):
        deduplicator_pipeline.process_item(sample_item, None)  # Duplicate raises DropItem


def test_deduplicator_pipeline_multiple_items(deduplicator_pipeline):
    """
    Verify that multiple unique items are processed without errors.
    """
    item1 = {"url": "http://example.com/1"}
    item2 = {"url": "http://example.com/2"}

    result1 = deduplicator_pipeline.process_item(item1, None)
    result2 = deduplicator_pipeline.process_item(item2, None)

    assert result1 == item1
    assert result2 == item2


def test_deduplicator_pipeline_clean_state():
    """
    Verify that a new instance of DeDeuplicatorPipeline starts with a clean state.
    """
    pipeline1 = DeDeuplicatorPipeline()
    pipeline2 = DeDeuplicatorPipeline()

    item = {"url": "http://example.com/1"}

    # First pipeline processes the item
    result = pipeline1.process_item(item, None)
    assert result == item

    # Second pipeline should also process the same item as it has a clean state
    result = pipeline2.process_item(item, None)
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
def test_deduplicator_pipeline(items, urls_seen_length):
    pl = DeDeuplicatorPipeline()

    with suppress(DropItem):
        for item in items:
            pl.process_item(item, None)

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
