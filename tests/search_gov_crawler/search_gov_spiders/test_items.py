from datetime import UTC, datetime

import pytest

from search_gov_crawler.search_gov_spiders.items import (
    FreshnessSpiderException,
    FreshnessSpiderExceptionItem,
    FreshnessSpiderItem,
    FreshnessSpiderMarkedForDeletionItem,
    FreshnessSpiderNotMarkedForDeletionItem,
    SearchGovSpidersItem,
)


def test_search_gov_spiders_item():
    item = SearchGovSpidersItem(
        response_bytes=b"this is some bytes",
        url="https://www.example.com",
        output_target="opensearch",
        response_language="en",
        content_type="text/html",
    )

    assert item["response_bytes"] == b"this is some bytes"
    assert item["url"] == "https://www.example.com"
    assert item["output_target"] == "opensearch"
    assert item["response_language"] == "en"
    assert (
        str(item)
        == "Item(url=https://www.example.com, output_target=opensearch, content_type=text/html, response_language=en)"
    )


@pytest.fixture(name="freshness_spider_marked_for_deletion_item")
def fixture_freshness_spider_marked_for_deletion_item():
    return FreshnessSpiderMarkedForDeletionItem(
        checked_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        result="404",
        status_code="404",
        index_name="test_index",
        id="test_id",
        path="test_path",
        domain_name="test_domain",
    )


@pytest.fixture(name="freshness_spider_not_marked_for_deletion_item")
def fixture_freshness_spider_not_marked_for_deletion_item():
    return FreshnessSpiderNotMarkedForDeletionItem(
        checked_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        result="403",
        status_code="403",
        index_name="test_index",
        id="test_id",
        path="test_path",
        domain_name="test_domain",
    )


@pytest.fixture(name="freshness_spider_exception_item")
def fixture_freshness_spider_exception_item():
    return FreshnessSpiderExceptionItem(
        checked_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        result="success",
        index_name="test_index",
        id="test_id",
        path="test_path",
        domain_name="test_domain",
        exception=FreshnessSpiderException(exception_type="TestError", exception_message="Test Exception"),
    )


FRESHNESS_SPIDER_ITEM_TEST_CASES = [
    (
        "freshness_spider_marked_for_deletion_item",
        {
            "checked_at": datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            "result": "404",
            "marked_for_deletion": True,
            "status_code": "404",
            "index_name": "test_index",
            "id": "test_id",
            "path": "test_path",
            "domain_name": "test_domain",
            "exception": None,
        },
    ),
    (
        "freshness_spider_not_marked_for_deletion_item",
        {
            "checked_at": datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            "result": "403",
            "marked_for_deletion": False,
            "status_code": "403",
            "index_name": "test_index",
            "id": "test_id",
            "path": "test_path",
            "domain_name": "test_domain",
            "exception": None,
        },
    ),
    (
        "freshness_spider_exception_item",
        {
            "checked_at": datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            "result": "success",
            "marked_for_deletion": False,
            "status_code": None,
            "index_name": "test_index",
            "id": "test_id",
            "path": "test_path",
            "domain_name": "test_domain",
            "exception": {
                "exception_type": "TestError",
                "exception_message": "Test Exception",
            },
        },
    ),
]


@pytest.mark.parametrize(("item_fixture", "data_out"), FRESHNESS_SPIDER_ITEM_TEST_CASES)
def test_freshness_spider_item(request, item_fixture, data_out):
    assert request.getfixturevalue(item_fixture).to_dict() == data_out


def test_freshness_spider_item_generate_template():
    assert FreshnessSpiderItem.generate_template() == {
        "mappings": {
            "properties": {
                "checked_at": {"type": "date"},
                "result": {"type": "keyword"},
                "marked_for_deletion": {"type": "boolean"},
                "status_code": {"type": "keyword"},
                "index_name": {"type": "keyword"},
                "id": {"type": "keyword"},
                "path": {"type": "keyword"},
                "domain_name": {"type": "keyword"},
                "exception": {
                    "properties": {
                        "exception_type": {"type": "keyword"},
                        "exception_message": {"type": "text"},
                    }
                },
            }
        },
        "settings": {"number_of_replicas": 1, "number_of_shards": 2},
    }
