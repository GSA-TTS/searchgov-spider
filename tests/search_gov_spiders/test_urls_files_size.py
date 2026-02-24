import copy
import os

import pytest
from scrapy import Spider
from scrapy.crawler import Crawler
from scrapy.utils.reactor import install_reactor
from scrapy.utils.test import get_crawler

from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem
from search_gov_crawler.search_gov_spiders.pipelines import SearchGovSpidersPipeline


@pytest.fixture(name="intsall_reactor", autouse=True)
def fixture_install_reactor():
    install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")

@pytest.fixture(name="sample_crawler")
def fixture_sample_crawler() -> Crawler:
    crawler = get_crawler(Spider)
    spider = Spider.from_crawler(
        crawler=crawler,
        name="urls_test",
        allow_query_string=True,
        allowed_domains="example.com",
        output_target="endpoint",
    )
    crawler.spider = spider
    return crawler


@pytest.fixture(name="sample_item")
def fixture_sample_item() -> SearchGovSpidersItem:
    """Fixture for a sample item with a URL."""
    item = SearchGovSpidersItem()
    item["url"] = "http://example.com"
    item["output_target"] = "endpoint"
    return item


@pytest.fixture(name="sample_item_long")
def fixture_sample_item_long() -> SearchGovSpidersItem:
    """Fixture for a longer sample item to make triggering rotate a bit easier"""
    item = SearchGovSpidersItem()
    item["url"] = f"http://example.com/this/is/a/{'really/' * 141}long/url"  # len 1024
    item["output_target"] = "endpoint"
    return item


@pytest.fixture(name="mock_open")
def fixture_mock_open(mocker):
    return mocker.patch("builtins.open", mocker.mock_open())


@pytest.fixture(name="pipeline_no_api")
def fixture_pipeline_no_api(mock_open, mocker, sample_crawler) -> SearchGovSpidersPipeline:
    mocker.patch.dict(os.environ, {})
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.SearchGovSpidersPipeline.APP_PID", 1234)
    return SearchGovSpidersPipeline.from_crawler(sample_crawler)


@pytest.fixture(name="pipeline_with_api")
def fixture_pipeline_with_api(mocker, sample_crawler) -> SearchGovSpidersPipeline:
    """Fixture for pipeline with an API URL set."""
    mocker.patch.dict(os.environ, {"SPIDER_URLS_API": "http://mockapi.com"})
    mocker.patch("search_gov_crawler.search_gov_spiders.pipelines.SearchGovSpidersPipeline.APP_PID", 1234)

    return SearchGovSpidersPipeline.from_crawler(sample_crawler)


def test_write_to_file(pipeline_no_api, mock_open, sample_item, mocker):
    """Test that URLs are written to files when SPIDER_URLS_API is not set."""
    sample_item_copy = copy.deepcopy(sample_item)
    sample_item_copy["output_target"] = "csv"
    mocker.patch.object(SearchGovSpidersPipeline, "_file_size", return_value=100)
    pipeline_no_api.process_item(sample_item_copy)

    assert "html_content" not in sample_item_copy, f"Key 'html_content' should not be in the item after it's processed"
    assert "output_target" not in sample_item_copy, f"Key 'output_target' should not be in the item after it's processed"

    # Ensure file is opened and written to
    mock_open.assert_called_once_with(pipeline_no_api.file_path, "a", encoding="utf-8")
    mock_open().write.assert_any_call(sample_item_copy["url"] + "\n")


def test_post_to_api(pipeline_with_api, sample_item, mocker):
    """Test that URLs are batched and sent via POST when SPIDER_URLS_API is set."""
    mock_post = mocker.patch("requests.post")
    sample_item_copy = copy.deepcopy(sample_item)
    pipeline_with_api.process_item(sample_item_copy)
    sample_item_copy["output_target"] = "endpoint"

    # Check that the batch contains the URL
    assert sample_item_copy["url"] in pipeline_with_api.urls_batch

    # Simulate max size to force post
    mocker.patch.object(
        SearchGovSpidersPipeline,
        "_batch_size",
        return_value=SearchGovSpidersPipeline.MAX_URL_BATCH_SIZE_BYTES,
    )
    pipeline_with_api.process_item(sample_item_copy)

    # Ensure POST request was made
    mock_post.assert_called_once_with("http://mockapi.com", json={"urls": pipeline_with_api.urls_batch})


def test_rotate_file(pipeline_no_api, mock_open, sample_item, mocker):
    """Test that file rotation occurs when max size is exceeded."""
    sample_item["output_target"] = "csv"
    mock_rename = mocker.patch("os.rename")
    mocker.patch.object(
        SearchGovSpidersPipeline,
        "_file_size",
        return_value=SearchGovSpidersPipeline.MAX_URL_BATCH_SIZE_BYTES,
    )
    pipeline_no_api.process_item(sample_item)

    # Check if the file was rotated
    mock_open.assert_called_with(pipeline_no_api.file_path, "a", encoding="utf-8")
    mock_open().close.assert_called()
    mock_rename.assert_called_once()


def test_post_to_api_size_limit(pipeline_with_api, mocker, sample_item_long):
    """Validate size limit checking with API calls enabled"""
    mock_post = mocker.patch("requests.post")

    for _ in range(200):
        pipeline_with_api.process_item(sample_item_long)
        sample_item_long["output_target"] = "endpoint"

    pipeline_with_api.close_spider()
    # Ensure POST request was made
    calls = [
        mocker.call("http://mockapi.com", json=mocker.ANY),
        mocker.call().raise_for_status(),
        mocker.call("http://mockapi.com", json=mocker.ANY),
        mocker.call().raise_for_status(),
    ]
    mock_post.assert_has_calls(calls)


def test_post_urls_on_spider_close(pipeline_with_api, mocker):
    """Test that remaining URLs are posted when spider closes and SPIDER_URLS_API is set."""
    mock_post = mocker.patch("requests.post")

    pipeline_with_api.urls_batch = ["http://example.com"]
    pipeline_with_api.close_spider()

    # Ensure POST request was made on spider close, cannot verify json once urls_batch is cleared
    mock_post.assert_called_once_with("http://mockapi.com", json=mocker.ANY)
