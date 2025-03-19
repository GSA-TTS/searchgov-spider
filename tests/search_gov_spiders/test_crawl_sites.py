from pathlib import Path

import pytest

from search_gov_crawler.search_gov_spiders.crawl_sites import CrawlSite, CrawlSites


@pytest.fixture(name="base_crawl_site_args")
def fixture_base_crawl_site_args() -> dict:
    return {
        "name": "test",
        "allow_query_string": True,
        "allowed_domains": "example.com",
        "handle_javascript": False,
        "output_target": "csv",
        "starting_urls": "https://www.example.com",
        "depth_limit": 3,
    }


@pytest.mark.parametrize("schedule", [None, "* * * * *"])
def test_valid_crawl_site(schedule, base_crawl_site_args):
    test_args = base_crawl_site_args
    if schedule:
        test_args["schedule"] = schedule

    assert isinstance(CrawlSite(**test_args), CrawlSite)


@pytest.mark.parametrize("exclude", [(), ("name",)])
def test_crawl_site_to_dict(base_crawl_site_args, exclude):
    cs = CrawlSite(**base_crawl_site_args)
    output = cs.to_dict(exclude=exclude)
    expected_output = base_crawl_site_args | {"schedule": None}

    for field in exclude:
        expected_output.pop(field)

    assert isinstance(output, dict)
    assert output == expected_output


@pytest.mark.parametrize(
    "fields",
    [
        ("name",),
        ("allow_query_string",),
        ("allowed_domains",),
        ("handle_javascript", "starting_urls"),
    ],
)
def test_invalid_crawl_site_missing_field(fields, base_crawl_site_args):
    test_args = base_crawl_site_args | {"schedule": "* * * * *"}

    for field in fields:
        test_args[field] = None

    match = f"All CrawlSite fields are required!  Add values for {','.join(fields)}"
    with pytest.raises(TypeError, match=match):
        CrawlSite(**test_args)


@pytest.mark.parametrize(
    ("field", "new_value", "expected_type"),
    [
        ("name", 123, str),
        ("allow_query_string", "string val", bool),
        ("allowed_domains", True, str),
        ("handle_javascript", 99.99, bool),
        ("starting_urls", {"some": "dict"}, str),
    ],
)
def test_invalid_crawl_site_wrong_type(
    base_crawl_site_args, field, new_value, expected_type
):
    test_args = base_crawl_site_args | {"schedule": "* * * * *"}
    test_args[field] = new_value

    match = f"Invalid type! Field {field} with value {new_value} must be type {expected_type}"
    with pytest.raises(TypeError, match=match):
        CrawlSite(**test_args)


@pytest.mark.parametrize(
    ("field", "new_value", "expected_type"),
    [
        ("output_target", "index", {"endpoint", "elasticsearch", "csv"}),
    ],
)
def test_invalid_crawl_site_output_target(
    base_crawl_site_args, field, new_value, expected_type
):
    test_args = base_crawl_site_args | {field: new_value}

    match = f"Invalid output_target value {new_value}! Must be one of {expected_type}"
    with pytest.raises(TypeError, match=match):
        CrawlSite(**test_args)


def test_valid_crawl_sites(base_crawl_site_args):
    cs = CrawlSites([CrawlSite(**base_crawl_site_args)])

    assert isinstance(cs.root, list)
    assert isinstance(cs.root[0], CrawlSite)
    assert list(cs.root) == list(cs)


def test_valid_crawl_sites_from_file(crawl_sites_test_file):
    cs = CrawlSites.from_file(file=crawl_sites_test_file)

    assert len(list(cs)) == 4


def test_valid_crawl_sites_scheduled(base_crawl_site_args):
    different_crawl_site_args = base_crawl_site_args | {
        "allowed_domains": "another.example.com",
        "schedule": "* * * * *",
        "starting_urls": "https://another.example.com",
        "depth_limit": 3,
    }

    test_input = [
        CrawlSite(**base_crawl_site_args),
        CrawlSite(**different_crawl_site_args),
    ]

    cs = CrawlSites(test_input)
    assert len(list(cs.scheduled())) == 1


def test_invalid_crawl_sites_duplicates(base_crawl_site_args):
    with pytest.raises(
        TypeError,
        match="The combination of allowed_domain and starting_urls must be unique in file!",
    ):
        CrawlSites(
            [CrawlSite(**base_crawl_site_args), CrawlSite(**base_crawl_site_args)]
        )


@pytest.mark.parametrize(
    "file_name",
    [
        "crawl-sites-development.json",
        "crawl-sites-staging.json",
        "crawl-sites-production.json",
    ],
)
def test_crawl_sites_file_is_valid(file_name):
    """
    Read in the actual crawl-sites-sample.json file and instantiate as a CrawlSites class.  This will run all built-in
    validations and hopefully let you know if the file is invalid prior to attempting to run it in the scheduler.
    Additionally, we are assuming that there is at least one scheduled job in the file.
    """

    crawl_sites_file = (
        Path(__file__).parent.parent.parent
        / "search_gov_crawler"
        / "domains"
        / file_name
    )

    cs = CrawlSites.from_file(file=crawl_sites_file)
    assert len(list(cs.scheduled())) > 0
