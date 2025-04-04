from collections import namedtuple

import pytest

from search_gov_crawler.search_gov_spiders.helpers import domain_spider as helpers
from search_gov_crawler.search_gov_spiders.spiders.domain_spider_js import should_abort_request


@pytest.mark.parametrize(
    ("content_type_header", "result"),
    [("text/html", True), ("application/msword.more.and.more", True), ("Something/Else", False)],
    ids=["good", "regex", "bad"],
)
def test_is_valid_content_type(content_type_header, result):
    assert helpers.is_valid_content_type(content_type_header, "csv") is result


def test_get_crawl_sites_test_file(crawl_sites_test_file):
    assert len(helpers.get_crawl_sites(str(crawl_sites_test_file.resolve()))) == 4


@pytest.mark.parametrize(("handle_javascript", "results"), [(True, 2), (False, 2)])
def test_default_starting_urls(monkeypatch, crawl_sites_test_file_json, handle_javascript, results):
    def mock_get_crawl_sites(*_args, **_kwargs):
        return crawl_sites_test_file_json

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_spiders.helpers.domain_spider.get_crawl_sites", mock_get_crawl_sites
    )

    starting_urls = helpers.default_starting_urls(handle_javascript)
    assert len(starting_urls) == results


@pytest.mark.parametrize(("handle_javascript", "results"), [(True, 2), (False, 2)])
def test_default_allowed_domains(monkeypatch, crawl_sites_test_file_json, handle_javascript, results):
    def mock_get_crawl_sites(*_args, **_kwargs):
        return crawl_sites_test_file_json

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_spiders.helpers.domain_spider.get_crawl_sites", mock_get_crawl_sites
    )

    allowed_domains = helpers.default_allowed_domains(handle_javascript=handle_javascript)
    assert len(allowed_domains) == results


@pytest.mark.parametrize(
    ("remove_paths", "results"),
    [
        (False, ["quotes.toscrape.com", "quotes.toscrape.com/tag/"]),
        (True, ["quotes.toscrape.com", "quotes.toscrape.com"]),
    ],
)
def test_default_allowed_domains_remove_paths(monkeypatch, crawl_sites_test_file_json, remove_paths, results):
    def mock_get_crawl_sites(*_args, **_kwargs):
        return crawl_sites_test_file_json

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_spiders.helpers.domain_spider.get_crawl_sites", mock_get_crawl_sites
    )

    allowed_domains = helpers.default_allowed_domains(handle_javascript=False, remove_paths=remove_paths)
    assert allowed_domains == results


Request = namedtuple("Request", ["resource_type", "should_abort"])


@pytest.fixture(name="request_with_resource_type", params=[("jpeg", True), ("html", False)], ids=["Valid", "Invalid"])
def fixture_request_with_resource_type(request) -> Request:
    return Request(*request.param)


def test_should_abort_request(request_with_resource_type):
    assert should_abort_request(request_with_resource_type) == request_with_resource_type.should_abort


def test_split_allowed_domains():
    assert helpers.split_allowed_domains("test.com,example.com/home") == ["test.com", "example.com"]


@pytest.mark.parametrize(
    ("deny_paths", "expected_output"),
    [
        (None, helpers.LINK_DENY_REGEX_STR),
        ("", helpers.LINK_DENY_REGEX_STR),
        ("path1", helpers.LINK_DENY_REGEX_STR | {"path1"}),
        ("path1,path1", helpers.LINK_DENY_REGEX_STR | {"path1"}),
        ("path1,PATH1", helpers.LINK_DENY_REGEX_STR | {"path1", "PATH1"}),
        ("path1,path2", helpers.LINK_DENY_REGEX_STR | {"path1", "path2"}),
    ],
)
def test_set_link_extractor_deny(deny_paths, expected_output):
    assert helpers.set_link_extractor_deny(deny_paths) == expected_output
