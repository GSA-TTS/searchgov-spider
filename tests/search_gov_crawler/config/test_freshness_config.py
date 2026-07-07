from dataclasses import asdict
from pathlib import Path

import pytest

from search_gov_crawler.config.freshness.freshness_config import (
    FreshnessCheckerConfig,
    FreshnessCheckerConfigs,
    FreshnessCheckerValidationError,
)


@pytest.fixture(name="base_kwargs")
def fixture_base_kwargs():
    return {
        "name": "test-spider",
        "schedule": "* * * * *",
        "query": {"test": "query"},
    }


@pytest.mark.parametrize(
    ("max_results_in", "max_results_out"),
    [(None, ""), (100, "100"), ("100", "100")],
)
def test_freshness_checker_config(base_kwargs, max_results_in, max_results_out):
    input_kwargs = {**base_kwargs, "max_results": max_results_in}
    config = FreshnessCheckerConfig(**input_kwargs)
    assert asdict(config) == {**input_kwargs, "max_results": max_results_out}


@pytest.mark.parametrize(("field", "invalid_value"), [("name", 123), ("schedule", 123), ("query", 123)])
def test_freshness_checker_config_type_validation(base_kwargs, field, invalid_value):
    input_kwargs = {**base_kwargs, "max_results": "100"}
    input_kwargs[field] = invalid_value
    with pytest.raises(FreshnessCheckerValidationError, match="Invalid type"):
        FreshnessCheckerConfig(**input_kwargs)


def test_freshness_checker_config_invalid_schedule(base_kwargs):
    input_kwargs = {**base_kwargs, "max_results": "100"}
    input_kwargs["schedule"] = "THIS IS NOT A CRON EXPRESSION!!!"
    with pytest.raises(FreshnessCheckerValidationError, match="Invalid cron expression in schedule"):
        FreshnessCheckerConfig(**input_kwargs)


def test_freshness_checker_configs(base_kwargs):
    input_kwargs = {**base_kwargs, "max_results": "100"}

    fs = FreshnessCheckerConfigs([FreshnessCheckerConfig(**input_kwargs), FreshnessCheckerConfig(**input_kwargs)])
    assert len(list(fs)) == 2


@pytest.mark.parametrize(
    "filename",
    [
        "freshness-checker-development.json",
        "freshness-checker-staging.json",
        "freshness-checker-production.json",
    ],
)
def test_freshness_checker_files_are_valid(filename):
    """
    Read in the actual freshness-checker config files and instantiate as a FreshnessCheckerConfigs class.  This will
    run all built-in validations and hopefully let you know if the file is invalid prior to attempting to run it in
    the scheduler. Additionally, we are assuming that there is at least one scheduled checker in each file.
    """
    frehness_checker_file = (
        Path(__file__).parent.parent.parent.parent / "search_gov_crawler" / "config" / "freshness" / filename
    )
    fs = FreshnessCheckerConfigs.from_file(file=frehness_checker_file)
    assert len(list(fs)) > 0
