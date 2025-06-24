import argparse

import pytest
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.blocking import BlockingScheduler

from search_gov_crawler.dap.schedule import ensure_positive_int, init_scheduler


@pytest.fixture(name="scheduler")
def fixture_init_scheduler() -> BlockingScheduler:
    return init_scheduler()


def test_init_scheduler(scheduler):
    # ensure config does not change without a failure here
    assert isinstance(scheduler, BlockingScheduler)


@pytest.mark.parametrize(("attr", "attr_type"), [("_executors", ThreadPoolExecutor), ("_jobstores", MemoryJobStore)])
def test_init_scheduler_config(scheduler, attr, attr_type):
    assert isinstance(getattr(scheduler, attr)["default"], attr_type)


def test_init_scheduler_defaults(scheduler):
    assert scheduler._job_defaults == {
        "misfire_grace_time": None,
        "coalesce": True,
        "max_instances": 1,
    }


@pytest.mark.parametrize("valid_value", [1, "2", "100", 200])
def test_ensure_positive_int(valid_value):
    assert ensure_positive_int(valid_value) == int(valid_value)


@pytest.mark.parametrize("invalid_value", [-1, "asdf", {"hi": "there"}, None])
def test_ensure_positive_int_invalid(invalid_value):
    with pytest.raises(argparse.ArgumentTypeError):
        ensure_positive_int(invalid_value)
