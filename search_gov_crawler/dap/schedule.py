import argparse
import logging

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.blocking import BlockingScheduler

log = logging.getLogger(__name__)


def init_scheduler() -> BlockingScheduler:
    """Initialize in memory scheduler with capacity to run a single job at a time."""

    return BlockingScheduler(
        jobstores={"default": MemoryJobStore()},
        executors={"default": ThreadPoolExecutor(1)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": None},
        timezone="UTC",
    )


def ensure_positive_int(arg_in: str | int) -> int:
    """
    Validates that the input is a positive integer.
    """
    error_msg = f"{arg_in} is an invalid positive int value"

    try:
        argument = int(arg_in)
    except (TypeError, ValueError) as err:
        raise argparse.ArgumentTypeError(error_msg) from err

    if argument < 1:
        raise argparse.ArgumentTypeError(error_msg)
    return argument
