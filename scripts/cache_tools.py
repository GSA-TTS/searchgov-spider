"""
This script provides functionality to view and clear jobs in the Redis job store.
It includes commands to show all jobs, show pending jobs, show run times,
and clear pending jobs.

Usage:
    python cache_tools.py <command>
    where <command> is one of:
        - clear-pending-jobs: Clear all pending jobs from the Redis job store.
        - show-all-jobs: Show all jobs in the Redis job store.
        - show-pending-jobs: Show pending jobs in the Redis job store.
        - show-run-times: Show run times of jobs in the Redis job store.
"""

import argparse
from datetime import UTC, datetime

from redis import Redis

from search_gov_crawler.scheduling.redis import init_redis_client


def print_headers(key: str, results: list) -> None:
    """Print the headers for the given key and results."""
    print("-" * 80)
    print(f"Key:  {key}")
    print(f"Jobs: {len(results)}")
    print("-" * 80)


def print_all_jobs(redis: Redis, key: str) -> None:
    """Print all jobs from the give redis key."""
    results = redis.hgetall(key)
    print_headers(key=key, results=results)
    print(f"{'Job Id':<80}")
    print("-" * 80)
    for job_id, _job in results.items():
        print(f"{job_id.decode('utf-8'):<80}")


def print_sorted_set(redis: Redis, key: str, score_title: str, start: int = 0, end: int = -1) -> None:
    """Get the pending jobs from the Redis job store."""
    results = redis.zrange(name=key, start=start, end=end, withscores=True)

    print_headers(key=key, results=results)
    print(f"{'Job Id':<50} {score_title:<30}")
    print("-" * 80)
    for job_id, next_run_ts in results:
        next_run_datetime = datetime.fromtimestamp(next_run_ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S %Z")
        print(f"{job_id.decode('utf-8'):<50} {next_run_datetime:<30}")


def clear_pending_jobs(redis: Redis, key: str) -> None:
    """Clear the pending jobs from the Redis job store."""
    redis.delete(key)
    print(f"Cleared all pending jobs from key {key}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Redis job store tools")
    parser.add_argument(
        "command",
        type=str,
        choices=["clear-pending-jobs", "show-all-jobs", "show-pending-jobs", "show-run-times"],
        help="Command to execute",
    )
    args = parser.parse_args()

    redis_client = init_redis_client()
    match args.command:
        case "clear-pending-jobs":
            clear_pending_jobs(redis=redis_client, key="spider.schedule.pending_jobs")
        case "show-all-jobs":
            all_jobs_args = {"key": "spider.schedule.jobs"}
            print_all_jobs(redis=redis_client, **all_jobs_args)
        case "show-pending-jobs":
            pending_job_args = {"key": "spider.schedule.pending_jobs", "score_title": "Time Added to Queue"}
            print_sorted_set(redis=redis_client, **pending_job_args)
        case "show-run-times":
            run_time_args = {"key": "spider.schedule.run_times", "score_title": "Next Run Time"}
            print_sorted_set(redis=redis_client, **run_time_args)
