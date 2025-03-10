"""
Allow benchmarking and testing of spider.  Run this script in one of two ways:
- For a single non-js domain:
  - Run `python benchmark.py -d example.com -u 'https://www.example.com'`

- For multiple domains, specify a json file as input:
  - Run `python benchmark.py -f ./example_input_file.json
  - Input file should be a json array of objects in the same format as our crawl-sites-sample.json file:
    [
      {
        "name": "Example",
        "allowed_domains": "example.com",
        "allow_query_string": false,
        "handle_javascript": false,
        "schedule": null,
        "output_target": "csv",
        "starting_urls": "https://www.example.com"
      }
    ]
  - Values in schedule are ignored for benchmark runs.

- Run `python benchmark.py -h` or review code below for more details on arguments
"""

import argparse
import logging
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from pythonjsonlogger.json import JsonFormatter

from search_gov_crawler import scrapy_scheduler
from search_gov_crawler.elasticsearch.es_batch_upload import SearchGovElasticsearch
from search_gov_crawler.search_gov_spiders.crawl_sites import CrawlSites
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT
from search_gov_crawler.search_gov_spiders.helpers.domain_spider import ALLOWED_CONTENT_TYPE_OUTPUT_MAP

load_dotenv()

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))

log = logging.getLogger("search_gov_crawler.benchmark")


def init_scheduler() -> BackgroundScheduler:
    """
    Create and return instance of scheduler.  Set `max_workers`, i.e. the maximum number of spider
    processes this scheduler will spawn at one time to either the value of an environment variable
    or the default value from pythons concurrent.futures ThreadPoolExecutor.
    """

    # Initalize scheduler - 'min(32, (os.cpu_count() or 1) + 4)' is default from concurrent.futures
    # but set to default of 5 to ensure consistent numbers between environments and for schedule
    max_workers = int(os.environ.get("SPIDER_SCRAPY_MAX_WORKERS", "5"))
    log.info("Max workers for schedule set to %s", max_workers)

    return BackgroundScheduler(
        jobstores={"memory": MemoryJobStore()},
        executors={"default": ThreadPoolExecutor(max_workers)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": None},
        timezone="UTC",
    )


def create_apscheduler_job(
    name: str,
    allow_query_string: bool,
    allowed_domains: str,
    starting_urls: str,
    handle_javascript: bool,
    output_target: str,
    runtime_offset_seconds: int,
) -> dict:
    """Creates job record in format needed by apscheduler"""

    job_name = f"benchmark - {name}"

    return {
        "func": scrapy_scheduler.run_scrapy_crawl,
        "id": job_name,
        "name": job_name,
        "next_run_time": datetime.now(tz=UTC) + timedelta(seconds=runtime_offset_seconds),
        "args": [
            "domain_spider" if not handle_javascript else "domain_spider_js",
            allow_query_string,
            allowed_domains,
            starting_urls,
            output_target,
        ],
    }


def benchmark_from_file(input_file: Path, runtime_offset_seconds: int):
    """
    Run a benchmark process using input from a file.

    The maximum number of jobs allowed to run at once is set by the scheduler but here we control
    how jobs not yet running behave.  The `max_instance` arg ensures only a single job with a given
    id can run at one time. The `misfire_grace_time` and `coalesce` args, ensure that jobs are
    automatically run as soon as possible even if they have missed their scheduled time because of
    other constraints, such as too many other concurrent jobs, and that if they have missed multiple
    runs, they are only run once.
    """

    if not input_file.exists():
        msg = f"Input file {input_file} does not exist!"
        raise FileNotFoundError(msg)

    msg = "Starting benchmark from file! input_file=%s runtime_offset_seconds=%s"
    log.info(msg, input_file.name, runtime_offset_seconds)
    crawl_sites = CrawlSites.from_file(file=input_file)

    scheduler = init_scheduler()
    for crawl_site in crawl_sites:
        apscheduler_job = create_apscheduler_job(
            runtime_offset_seconds=runtime_offset_seconds,
            **crawl_site.to_dict(exclude=("schedule",)),
        )
        scheduler.add_job(**apscheduler_job, jobstore="memory")
    scheduler.start()
    time.sleep(runtime_offset_seconds + 2)
    scheduler.shutdown()  # this will wait until all jobs are finished


def benchmark_from_args(
    allow_query_string: bool,
    allowed_domains: str,
    starting_urls: str,
    handle_javascript: bool,
    output_target: str,
    runtime_offset_seconds: int,
):
    """Run an individual benchmarking job based on args"""

    msg = (
        "Starting benchmark from args! "
        "allow_query_string=%s allowed_domains=%s starting_urls=%s "
        "handle_javascript=%s output_target=%s runtime_offset_seconds=%s"
    )
    log.info(
        msg,
        allow_query_string,
        allowed_domains,
        starting_urls,
        handle_javascript,
        output_target,
        runtime_offset_seconds,
    )

    apscheduler_job_kwargs = {
        "name": "benchmark",
        "allow_query_string": allow_query_string,
        "allowed_domains": allowed_domains,
        "starting_urls": starting_urls,
        "handle_javascript": handle_javascript,
        "output_target": output_target,
        "runtime_offset_seconds": runtime_offset_seconds,
    }

    scheduler = init_scheduler()
    apscheduler_job = create_apscheduler_job(**apscheduler_job_kwargs)
    scheduler.add_job(**apscheduler_job, jobstore="memory")
    scheduler.start()
    time.sleep(runtime_offset_seconds + 2)
    scheduler.shutdown()  # wait until all jobs are finished


if __name__ == "__main__":
    no_input_arg = all(arg not in sys.argv for arg in ["-f", "--input_file"])

    parser = argparse.ArgumentParser(description="Run a scrapy schedule or benchmark based on input.")
    parser.add_argument("-f", "--input_file", type=str, help="Path to file containing list of domains to schedule")
    parser.add_argument("-d", "--allowed_domains", type=str, help="domains allowed to crawl", required=no_input_arg)
    parser.add_argument("-u", "--starting_urls", type=str, help="url used to start crawl", required=no_input_arg)
    parser.add_argument(
        "-o",
        "--output_target",
        type=str,
        help="Point the output of the crawls to a backend",
        required=no_input_arg,
        choices=list(ALLOWED_CONTENT_TYPE_OUTPUT_MAP.keys()),
    )
    parser.add_argument(
        "-js",
        "--handle_js",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Flag to enable javascript",
    )
    parser.add_argument(
        "-qs",
        "--allow_query_string",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Flag to enable capturing URLs with query strings",
    )
    parser.add_argument("-t", "--runtime_offset", type=int, default=5, help="Number of seconds to offset job start")
    args = parser.parse_args()

    if no_input_arg:
        benchmark_args = {
            "allow_query_string": args.allow_query_string,
            "allowed_domains": args.allowed_domains,
            "starting_urls": args.starting_urls,
            "handle_javascript": args.handle_js,
            "output_target": args.output_target,
            "runtime_offset_seconds": args.runtime_offset,
        }
        benchmark_from_args(**benchmark_args)
    else:
        benchmark_from_file(input_file=Path(args.input_file), runtime_offset_seconds=args.runtime_offset)
