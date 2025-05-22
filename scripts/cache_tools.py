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

from datetime import UTC, datetime

import click
from redis import Redis

from search_gov_crawler.scheduling.redis import init_redis_client

ALL_JOBS_KEY: str = "spider.schedule.jobs"
PENDING_JOBS_KEY: str = "spider.schedule.pending_jobs"
RUN_TIMES_KEY: str = "spider.schedule.run_times"
JOB_STATE_KEY_PATTERN: str = "spider.%(spider_id)s.%(key_type)s"


def print_headers(key: str, results: list, result_label: str = "Jobs") -> None:
    """Print the headers for the given key and results."""
    spacing = len(result_label)
    print("-" * 80)
    print(f"{'Key:':<{spacing}}  {key}")
    print(f"{result_label:<{spacing}}: {len(results)}")
    print("-" * 80)


def print_all_jobs(redis: Redis, key: str) -> None:
    """Print all jobs from the given redis key."""
    results = redis.hgetall(key)
    print_headers(key=key, results=results)
    print(f"{'Job Id':<80}")
    print("-" * 80)
    for job_id in results:
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


def print_scheduler_keys_and_size(redis: Redis, keys: list, key_pattern: str) -> None:
    """Capture and print the names and sizes of scheduler keys"""

    print_headers(key=key_pattern, results=keys, result_label="Count")
    if keys:
        print(f"{'Key Name':<50}{'Size':<30}")
        print("-" * 80)

        for key in keys:
            size = redis.llen(key) if redis.type(key) == "list" else redis.scard(key)
            print(f"{key:<50}{size:<30}")


def delete_key(redis: Redis, key: str) -> None:
    """Clear the given key from the redis cache."""
    redis.delete(key)
    print(f"Deleted key {key}")


@click.group()
def cli():
    """Redis job store tools."""
    pass


@cli.command()
def clear_pending_jobs():
    """Clear all pending jobs from the Redis job store."""
    redis_client = init_redis_client()

    if click.confirm(f"Are you sure you want to delete the key {PENDING_JOBS_KEY}"):
        delete_key(redis=redis_client, key=PENDING_JOBS_KEY)


@cli.command()
@click.option("--pending/--all", is_flag=True, help="Flag to show either pending or all (default) jobs.")
def show_jobs(pending):
    """Show jobs in the Redis job store."""
    redis_client = init_redis_client()
    if pending:
        print_sorted_set(redis=redis_client, key=PENDING_JOBS_KEY, score_title="Time Added to Queue")
    else:
        print_all_jobs(redis=redis_client, key=ALL_JOBS_KEY)


@cli.command()
def show_run_times():
    """Show run times of jobs in the Redis job store."""
    redis_client = init_redis_client()
    print_sorted_set(redis=redis_client, key=RUN_TIMES_KEY, score_title="Next Run Time")


@cli.command()
@click.option("-t", "--type", type=click.Choice(["requests", "dupefilter"], case_sensitive=False), required=True)
def show_job_state_keys(type):
    """Shows name and size of job state keys."""
    redis_client = init_redis_client(decode_responses=True)
    key_pattern = JOB_STATE_KEY_PATTERN % {"spider_id": "*", "key_type": type}
    keys = list(redis_client.scan_iter(key_pattern))
    print_scheduler_keys_and_size(redis=redis_client, keys=keys, key_pattern=key_pattern)


@cli.command()
@click.option("-id", "--spider_id", type=str, required=True)
@click.option("--apply", is_flag=True, default=False)
def delete_job_state_keys(spider_id: str, apply: bool):
    """Delete job state keys (requests and dupefilter) based on spider_id."""
    redis_client = init_redis_client(decode_responses=True)
    key_pattern = JOB_STATE_KEY_PATTERN % {"spider_id": spider_id, "key_type": "*"}
    keys = list(redis_client.scan_iter(key_pattern))
    print_scheduler_keys_and_size(redis=redis_client, keys=keys, key_pattern=key_pattern)

    if keys and apply:
        print("-" * 80)
        if click.confirm("Are you sure you want to delete these keys?"):
            for key in keys:
                delete_key(redis=redis_client, key=key)
    elif keys:
        print("Run command with --apply to delete these keys")


if __name__ == "__main__":
    cli()
