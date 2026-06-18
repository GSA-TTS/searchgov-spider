from search_gov_crawler.indexing.transform import set_metadata_fields
from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem


def test_set_metadata_fields():
    item = SearchGovSpidersItem(
        content_type="test/test",
        crawl_depth=1,
        creator="unit_test",
        download_milliseconds=100,
        output_target="opensearch",
        response_bytes=bytes("chomp chomp", "utf-8"),
        response_language="en",
        source_url="https://www.example.com",
        url="https://www.example.com/page1",
    )

    assert set_metadata_fields(item) == {
        "crawl_depth": 1,
        "creator": "unit_test",
        "download_bytes": 11,
        "download_milliseconds": 100,
        "source_url": "https://www.example.com",
    }


def test_set_metadata_fields_defaults():
    item = SearchGovSpidersItem(
        content_type="test/test",
        output_target="opensearch",
        response_language="en",
        url="https://www.example.com/page1",
    )
    assert set_metadata_fields(item) == {
        "crawl_depth": None,
        "creator": None,
        "download_bytes": 0,
        "download_milliseconds": None,
        "source_url": None,
    }
