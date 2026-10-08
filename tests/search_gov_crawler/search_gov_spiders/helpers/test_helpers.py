import re
from typing import NamedTuple

import pytest
from scrapy.spiders import Spider

import search_gov_crawler.search_gov_spiders.helpers.domain_spider as ds_helpers
from search_gov_crawler.search_gov_spiders.spiders.domain_spider_js import should_abort_request


@pytest.mark.parametrize(
    ("content_type_header", "output_target", "result"),
    [
        (None, None, None),
        ("text/html", "csv", "text/html"),
        ("text/html;extra/whatever", "csv", "text/html"),
        ("text/html;extra/whatever", "opensearch", "text/html"),
        ("application/msword", "opensearch", None),
    ],
)
def test_get_simple_content_type(mocker, content_type_header, output_target, result):
    mock_get_response_header = mocker.patch(
        "search_gov_crawler.search_gov_spiders.helpers.domain_spider.get_response_header"
    )
    mock_get_response_header.return_value = content_type_header
    assert ds_helpers.get_simple_content_type(mocker.Mock(), output_target) == result


def test_get_crawl_sites_test_file(crawl_sites_test_file):
    assert len(ds_helpers.get_crawl_sites(str(crawl_sites_test_file.resolve()))) == 4


def test_get_crawl_sites_no_input():
    assert len(ds_helpers.get_crawl_sites()) > 0


@pytest.mark.parametrize(
    ("download_latency", "download_milliseconds"),
    [(None, None), (0.12345, 123), (123456.7891, 123456789)],
)
def test_get_download_milliseconds(mocker, download_latency, download_milliseconds):
    mock_response = mocker.MagicMock()
    mock_response.meta.get.return_value = download_latency
    assert ds_helpers.get_download_milliseconds(response=mock_response) == download_milliseconds


@pytest.mark.parametrize(("handle_javascript", "results"), [(True, 2), (False, 2)])
def test_default_starting_urls(monkeypatch, crawl_sites_test_file_json, handle_javascript, results):
    def mock_get_crawl_sites(*_args, **_kwargs):
        return crawl_sites_test_file_json

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_spiders.helpers.domain_spider.get_crawl_sites",
        mock_get_crawl_sites,
    )

    starting_urls = ds_helpers.default_starting_urls(handle_javascript=handle_javascript)
    assert len(starting_urls) == results


@pytest.mark.parametrize(("handle_javascript", "results"), [(True, 2), (False, 2)])
def test_default_allowed_domains(monkeypatch, crawl_sites_test_file_json, handle_javascript, results):
    def mock_get_crawl_sites(*_args, **_kwargs):
        return crawl_sites_test_file_json

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_spiders.helpers.domain_spider.get_crawl_sites",
        mock_get_crawl_sites,
    )

    allowed_domains = ds_helpers.default_allowed_domains(handle_javascript=handle_javascript)
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
        "search_gov_crawler.search_gov_spiders.helpers.domain_spider.get_crawl_sites",
        mock_get_crawl_sites,
    )

    allowed_domains = ds_helpers.default_allowed_domains(handle_javascript=False, remove_paths=remove_paths)
    assert allowed_domains == results


class Request(NamedTuple):
    resource_type: str
    should_abort: bool


@pytest.fixture(name="request_with_resource_type", params=[("jpeg", True), ("html", False)], ids=["Valid", "Invalid"])
def fixture_request_with_resource_type(request) -> Request:
    return Request(*request.param)


def test_should_abort_request(request_with_resource_type):
    assert should_abort_request(request_with_resource_type) == request_with_resource_type.should_abort


def test_split_allowed_domains():
    assert ds_helpers.split_allowed_domains("test.com,example.com/home") == ["test.com", "example.com"]


@pytest.mark.parametrize(
    ("deny_paths", "expected_output"),
    [
        (None, ds_helpers.LINK_DENY_REGEX_STR),
        ("", ds_helpers.LINK_DENY_REGEX_STR),
        ("path1", ds_helpers.LINK_DENY_REGEX_STR | {"path1"}),
        ("path1,path1", ds_helpers.LINK_DENY_REGEX_STR | {"path1"}),
        ("path1,PATH1", ds_helpers.LINK_DENY_REGEX_STR | {"path1", "PATH1"}),
        ("path1,path2", ds_helpers.LINK_DENY_REGEX_STR | {"path1", "path2"}),
    ],
)
def test_set_link_extractor_deny(deny_paths, expected_output):
    assert ds_helpers.set_link_extractor_deny(deny_paths) == expected_output


def test_get_response_header(mocker):
    response = mocker.Mock()
    response.headers.get.side_effect = [None, bytes("test_value", "utf-8")]
    header = ds_helpers.get_response_header(response, "Test-Header")

    assert response.headers.get.call_count == 2
    assert header == "test_value"


@pytest.mark.parametrize(("content_language", "result"), [("en-US", "en"), (None, None)])
def test_get_response_language_code(mocker, content_language, result):
    mock_get_response_header = mocker.patch(
        "search_gov_crawler.search_gov_spiders.helpers.domain_spider.get_response_header"
    )
    mock_get_response_header.return_value = content_language
    assert ds_helpers.get_response_language_code(response=mocker.Mock()) == result


@pytest.mark.parametrize(
    ("input_args", "expected_spider_id"),
    [
        (("test1", 10, ["test1", "test2", "test3"]), "d918472fb4"),
        (("test2", 10, ["test1", "test2", "test3"]), "0b97ba301b"),
        (("test3",), "eeeac91190"),
    ],
)
def test_generate_spider_id_from_args(input_args, expected_spider_id):
    assert ds_helpers.generate_spider_id_from_args(*input_args) == expected_spider_id


def test_generate_spider_id_no_args():
    with pytest.raises(ValueError, match=re.escape("One or more arguments must be passed to generate a spider_id.")):
        ds_helpers.generate_spider_id_from_args()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("True", True),
        ("true", True),
        ("1", False),
        ("False", False),
        ("false", False),
        ("yes", False),
        (True, True),
        (False, False),
        (None, False),
    ],
)
def test_force_bool(value, expected):
    assert ds_helpers.force_bool(value) is expected


GET_DOMAIN_VISITS_TEST_CASES = [
    (["example.com"], {"test1.example.com": 100, "example.com": 200}),
    (
        ["example.com", "example2.com"],
        {"test1.example.com": 100, "example.com": 200, "test1.example2.com": 100, "example2.com": 200},
    ),
    (
        ["example.com", "example2.com", "test1.example.com"],
        {
            "test1.example.com": 200,
            "example.com": 200,
            "test1.example2.com": 100,
            "example2.com": 200,
            "subtest.test1.example.com": 100,
        },
    ),
    (["example.com", None, ""], {"test1.example.com": 100, "example.com": 200}),
]


@pytest.mark.parametrize(("allowed_domains", "expected_domain_visits"), GET_DOMAIN_VISITS_TEST_CASES)
def test_get_domain_visits(mocker, allowed_domains, expected_domain_visits):
    spider = Spider(
        name="test_spider",
        allowed_domains=allowed_domains,
        start_urls=["https://www.example.com"],
    )

    mocker.patch("search_gov_crawler.search_gov_spiders.helpers.domain_spider.init_redis_client")
    mock_avg_daily_vists = mocker.patch(
        "search_gov_crawler.search_gov_spiders.helpers.domain_spider.get_avg_daily_visits_by_domain",
    )
    mock_avg_daily_vists.side_effect = [
        {"test1.example.com": 100, "example.com": 200},
        {"test1.example2.com": 100, "example2.com": 200},
        {"subtest.test1.example.com": 100, "test1.example.com": 200},
    ]

    assert ds_helpers.get_domain_visits(spider) == expected_domain_visits
