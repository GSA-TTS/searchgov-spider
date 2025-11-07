import json
import re
from pathlib import Path

import pytest

from search_gov_crawler.search_gov_app.crawl_config import (
    CrawlConfig,
    CrawlConfigs,
    CrawlConfigsValidationError,
    CrawlConfigValidationError,
)


@pytest.fixture(name="base_crawl_config_args")
def fixture_base_crawl_config_args() -> dict:
    return {
        "name": "test",
        "allow_query_string": True,
        "allowed_domains": "example.com",
        "handle_javascript": False,
        "output_target": "csv",
        "starting_urls": "https://www.example.com",
        "depth_limit": 3,
    }


def test_valid_crawl_config(base_crawl_config_args):
    assert isinstance(CrawlConfig(**base_crawl_config_args), CrawlConfig)


@pytest.mark.parametrize(
    "optional_args",
    [
        {"schedule": None},
        {"schedule": "* * * 1 1"},
        {"deny_paths": None},
        {"deny_paths": ["/path1/", "/path2/"]},
    ],
)
def test_valid_crawl_config_optional_fields(base_crawl_config_args, optional_args):
    test_args = base_crawl_config_args | optional_args
    assert isinstance(CrawlConfig(**test_args), CrawlConfig)


@pytest.mark.parametrize("exclude", [(), ("name",)])
def test_crawl_config_to_dict(base_crawl_config_args, exclude):
    cs = CrawlConfig(**base_crawl_config_args)
    output = cs.to_dict(exclude=exclude)
    expected_output = base_crawl_config_args | {
        "schedule": None,
        "deny_paths": None,
        "check_sitemap_hours": None,
        "sitemap_urls": None,
        "job_id": cs.job_id,
    }

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
def test_invalid_crawl_config_missing_field(fields, base_crawl_config_args):
    test_args = base_crawl_config_args | {"schedule": "* * * * *"}

    for field in fields:
        test_args[field] = None

    match = f"All CrawlConfig fields are required!  Add values for {','.join(fields)}"
    with pytest.raises(CrawlConfigValidationError, match=match):
        CrawlConfig(**test_args)


@pytest.mark.parametrize(
    ("field", "new_value", "log_text", "expected_type"),
    [
        ("name", 123, "type", str),
        ("allow_query_string", "string val", "type", bool),
        ("allowed_domains", True, "type", str),
        ("handle_javascript", 99.99, "type", bool),
        ("starting_urls", {"some": "dict"}, "type", str),
        ("schedule", True, "one of types", ["str", "NoneType"]),
        ("deny_paths", 10, "one of types", ["list", "NoneType"]),
    ],
)
def test_invalid_crawl_config_wrong_type(base_crawl_config_args, field, new_value, log_text, expected_type):
    test_args = base_crawl_config_args | {"schedule": "* * * * *"}
    test_args[field] = new_value

    match = f"Invalid type! Field {field} with value {new_value} must be {log_text} {expected_type}"
    with pytest.raises(CrawlConfigValidationError, match=re.escape(match)):
        CrawlConfig(**test_args)


@pytest.mark.parametrize(
    ("field", "new_value", "expected_type"),
    [
        ("output_target", "index", ["csv", "endpoint", "elasticsearch"]),
    ],
)
def test_invalid_crawl_config_output_target(base_crawl_config_args, field, new_value, expected_type):
    test_args = base_crawl_config_args | {field: new_value}

    match = f"Invalid output_target value {new_value}! Must be one of {expected_type}"
    with pytest.raises(CrawlConfigValidationError, match=re.escape(match)):
        CrawlConfig(**test_args)


def test_invalid_crawl_config_duplicate_deny_path(base_crawl_config_args):
    test_args = base_crawl_config_args | {"deny_paths": ["/duplicate_path/", "/duplicate_path/"]}
    match = f"Values in deny_paths must be unique! {base_crawl_config_args['name']} has duplicates!"
    with pytest.raises(CrawlConfigValidationError, match=match):
        CrawlConfig(**test_args)


def test_valid_crawl_configs(base_crawl_config_args):
    cs = CrawlConfigs([CrawlConfig(**base_crawl_config_args)])

    assert isinstance(cs.root, list)
    assert isinstance(cs.root[0], CrawlConfig)
    assert list(cs.root) == list(cs)


def test_valid_crawl_configs_from_file(crawl_sites_test_file):
    cs = CrawlConfigs.from_file(file=crawl_sites_test_file)

    assert len(list(cs)) == len(json.loads(crawl_sites_test_file.read_text(encoding="UTF-8")))


def test_valid_crawl_configs_scheduled(base_crawl_config_args):
    different_crawl_config_args = base_crawl_config_args | {
        "name": "another test",
        "allowed_domains": "another.example.com",
        "schedule": "* * * * *",
        "starting_urls": "https://another.example.com",
        "depth_limit": 3,
    }

    test_input = [
        CrawlConfig(**base_crawl_config_args),
        CrawlConfig(**different_crawl_config_args),
    ]

    cs = CrawlConfigs(test_input)
    assert len(list(cs.scheduled())) == 1


def test_invalid_crawl_configs_duplicate_job_id(base_crawl_config_args):
    duplicate_job_id_args = base_crawl_config_args | {
        "allowed_domains": "test.example.com",
    }

    with pytest.raises(CrawlConfigsValidationError, match=r".*Duplicate job_id found.*"):
        CrawlConfigs([CrawlConfig(**base_crawl_config_args), CrawlConfig(**duplicate_job_id_args)])


def test_invalid_crawl_configs_duplicate_domain_in_target(base_crawl_config_args):
    duplicate_job_id_args = base_crawl_config_args | {"name": "test 2"}
    with pytest.raises(
        CrawlConfigsValidationError,
        match=r".*allowed_domain and output_target must be unique.*",
    ):
        CrawlConfigs([CrawlConfig(**base_crawl_config_args), CrawlConfig(**duplicate_job_id_args)])


def test_invalid_craw_sites_cron_expression(base_crawl_config_args):
    invalid_schedule_crawl_config_args = {"schedule": "I AM NOT A CRON EXPRESSION"} | base_crawl_config_args

    with pytest.raises(
        CrawlConfigValidationError, match="Invalid cron expression in schedule value: I AM NOT A CRON EXPRESSION"
    ):
        CrawlConfig(**invalid_schedule_crawl_config_args)


@pytest.mark.parametrize(
    "file_name",
    [
        "crawl-sites-development.json",
        "crawl-sites-staging.json",
        "crawl-sites-production.json",
    ],
)
def test_crawl_configs_file_is_valid(file_name):
    """
    Read in the actual crawl-sites-sample.json file and instantiate as a CrawlConfigs class.  This will run all built-in
    validations and hopefully let you know if the file is invalid prior to attempting to run it in the scheduler.
    Additionally, we are assuming that there is at least one scheduled job in the file.
    """

    crawl_sites_file = Path(__file__).parent.parent.parent / "search_gov_crawler" / "domains" / file_name

    cs = CrawlConfigs.from_file(file=crawl_sites_file)
    assert len(list(cs.scheduled())) > 0


@pytest.fixture(name="mock_database_connection")
def fixture_mock_database_connection(monkeypatch):
    def mock_get_database_connection(*_args, **_kwargs):
        class MockConnection:
            def __enter__(self):
                return True

            def __exit__(self, *args):
                return False

        return MockConnection()

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_app.crawl_config.get_database_connection",
        mock_get_database_connection,
    )


@pytest.fixture(name="valid_crawl_config")
def fixture_valid_crawl_config():
    return {
        "name": "test from db",
        "allow_query_string": 1,
        "allowed_domains": '["example.gov"]',
        "handle_javascript": 0,
        "output_target": "searchengine",
        "starting_urls": '["https://www.example.gov", "https://subdomain.example.gov"]',
        "depth_limit": 3,
        "schedule": "0 0 * * *",
        "deny_paths": '["path1/", "path2/"]',
        "check_sitemap_hours": None,
        "sitemap_urls": '["https://www.example.gov/sitemap.xml"]',
    }


@pytest.mark.usefixtures("mock_database_connection")
def test_crawl_configs_from_database(monkeypatch, valid_crawl_config):
    def mock_select_active_crawl_configs(*_args, **_kwargs):
        return [
            valid_crawl_config,
        ]

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_app.crawl_config.select_active_crawl_configs",
        mock_select_active_crawl_configs,
    )

    cs = CrawlConfigs.from_database()
    assert next(iter(cs)).to_dict() == {
        "name": "test from db",
        "allow_query_string": True,
        "allowed_domains": "example.gov",
        "handle_javascript": False,
        "output_target": "elasticsearch",
        "starting_urls": "https://www.example.gov,https://subdomain.example.gov",
        "depth_limit": 3,
        "schedule": "0 0 * * *",
        "deny_paths": ["path1/", "path2/"],
        "check_sitemap_hours": None,
        "sitemap_urls": ["https://www.example.gov/sitemap.xml"],
        "job_id": "test-from-db",
    }


@pytest.mark.usefixtures("mock_database_connection")
def test_crawl_configs_from_database_partially_valid(monkeypatch, valid_crawl_config, caplog):
    def mock_select_active_crawl_configs(*_args, **_kwargs):
        invalid_crawl_config = valid_crawl_config | {"schedule": "I AM NOT A CRON EXPRESSION"}
        return [invalid_crawl_config, valid_crawl_config]

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_app.crawl_config.select_active_crawl_configs",
        mock_select_active_crawl_configs,
    )

    with caplog.at_level("ERROR"):
        cs = CrawlConfigs.from_database()
        assert len(list(cs)) == 1
        assert "Invalid CrawlConfig record with name: test from db.  Skipping creation." in caplog.messages


@pytest.mark.usefixtures("mock_database_connection")
def test_crawl_configs_from_database_invalid(monkeypatch, valid_crawl_config, caplog):
    def mock_select_active_crawl_configs(*_args, **_kwargs):
        duplicate_name_crawl_config = valid_crawl_config | {"schedule": "1 1 * * *"}
        return [valid_crawl_config, duplicate_name_crawl_config]

    monkeypatch.setattr(
        "search_gov_crawler.search_gov_app.crawl_config.select_active_crawl_configs",
        mock_select_active_crawl_configs,
    )

    with caplog.at_level("ERROR"):
        cs = CrawlConfigs.from_database()
        assert len(list(cs)) == 0
        assert (
            "Could not create CrawlConfigs instance due to errors! No scheduler jobs will be created."
            in caplog.messages
        )
