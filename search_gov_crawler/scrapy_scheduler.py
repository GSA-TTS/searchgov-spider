"""
Starts scrapy scheduler.  Takes job details from the crawl_configs table in the searchgov database.

Use the env var SPIDER_SCRAPY_MAX_WORKERS to control how many jobs can run at once.  If the max number of
jobs are running when other jobs are supposed to run, those jobs will queue until one or more of the running
jobs finishes.
"""

import logging
import os
import subprocess
import time
from pathlib import Path

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_SUBMITTED
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from pythonjsonlogger.json import JsonFormatter

from search_gov_crawler.scheduling.jobstores import SpiderRedisJobStore
from search_gov_crawler.scheduling.redis import get_redis_connection_args
from search_gov_crawler.scheduling.schedulers import SpiderBackgroundScheduler
from search_gov_crawler.search_gov_app.crawl_config import CrawlConfigs
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT

load_dotenv()

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("search_gov_crawler.scrapy_scheduler")

CRAWL_CONFIGS_INTERVAL = int(os.environ.get("SPIDER_CRAWL_CONFIGS_CHECK_INTERVAL", "300"))  # in seconds
CRAWL_SITES_FILE = (
    Path(__file__).parent / "domains" / os.environ.get("SPIDER_CRAWL_SITES_FILE_NAME", "crawl-sites-production.json")
)


def run_scrapy_crawl(
    spider: str,
    allow_query_string: bool,
    allowed_domains: str,
    start_urls: str,
    output_target: str,
    depth_limit: int,
    deny_paths: list[str],
) -> None:
    """Runs `scrapy crawl` command as a subprocess given the allowed arguments"""

    scrapy_env = os.environ.copy()
    scrapy_env["PYTHONPATH"] = str(Path(__file__).parent.parent)

    cmd = (
        f"scrapy crawl {spider}"
        f" -a allow_query_string={allow_query_string}"
        f" -a allowed_domains={allowed_domains}"
        f" -a start_urls={start_urls}"
        f" -a output_target={output_target}"
        f" -a depth_limit={depth_limit}"
        f" -a deny_paths={','.join(deny_paths)}"
    )

    subprocess.run(
        cmd,
        check=True,
        cwd=Path(__file__).parent,
        env=scrapy_env,
        executable="/bin/bash",
        shell=True,
    )
    msg = (
        "Successfully completed scrapy crawl with args "
        "spider=%s, allow_query_string=%s, allowed_domains=%s, "
        "start_urls=%s, output_target=%s, depth_limit=%s, deny_paths=%s"
    )
    log.info(msg, spider, allow_query_string, allowed_domains, start_urls, output_target, depth_limit, deny_paths)


def transform_crawl_configs(crawl_configs: CrawlConfigs) -> list[dict]:
    """
    Transform crawl sites records into a format that can be used to create apscheduler jobs.  Only
    scheduler jobs that have a value for the `schedule` field.
    """

    transformed_crawl_configs = []

    for crawl_config in crawl_configs.scheduled():
        job_name = crawl_config.name
        transformed_crawl_configs.append(
            {
                "func": run_scrapy_crawl,
                "id": crawl_config.job_id,
                "name": job_name,
                "trigger": CronTrigger.from_crontab(expr=crawl_config.schedule, timezone="UTC"),
                "args": [
                    ("domain_spider" if not crawl_config.handle_javascript else "domain_spider_js"),
                    crawl_config.allow_query_string,
                    crawl_config.allowed_domains,
                    crawl_config.starting_urls,
                    crawl_config.output_target,
                    crawl_config.depth_limit,
                    crawl_config.deny_paths if crawl_config.deny_paths else [],
                ],
            },
        )

    return transformed_crawl_configs


def init_scheduler() -> SpiderBackgroundScheduler:
    """
    Create and return instance of scheduler.  Set `max_workers`, i.e. the maximum number of spider
    processes this scheduler will spawn at one time to either the value of an environment variable
    or the default value from pythons concurrent.futures ThreadPoolExecutor.
    """

    # Initalize scheduler - 'min(32, (os.cpu_count() or 1) + 4)' is default from concurrent.futures
    # but set to default of 5 to ensure consistent numbers between environments and for schedule
    max_workers = int(os.environ.get("SPIDER_SCRAPY_MAX_WORKERS", "5"))
    log.info("Max workers for schedule set to %s", max_workers)

    redis_connection_kwargs = get_redis_connection_args()

    return SpiderBackgroundScheduler(
        jobstores={
            "redis": SpiderRedisJobStore(
                jobs_key="spider.schedule.jobs",
                run_times_key="spider.schedule.run_times",
                pending_jobs_key="spider.schedule.pending_jobs",
                **redis_connection_kwargs,
            ),
        },
        executors={"default": ThreadPoolExecutor(max_workers)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": None},
        timezone="UTC",
    )


def keep_scheduler_alive() -> None:
    """
    Keeps the scheduler alive by sleeping in an infinite loop

    """
    while True:
        time.sleep(5)


def wait_for_next_interval(interval: int, *, keep_running: bool = True) -> bool:
    """
    Sleeps for the specified interval in seconds, then returns the keep_running value.

    """
    time.sleep(interval)
    log.debug("Woke up after sleeping for %s seconds", interval)
    return keep_running


def start_scrapy_scheduler_from_db():
    """
    Initializes schedule from database, schedules jobs and runs scheduler
    THIS IS FOR FUTURE USE - CURRENTLY NOT CALLED ANYWHERE
    """

    # Initialize Scheduler and add listeners
    scheduler = init_scheduler()
    scheduler.add_listener(scheduler.add_pending_job, EVENT_JOB_SUBMITTED)
    scheduler.add_listener(scheduler.remove_pending_job, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    scheduler.start(paused=True)

    try:
        # Load and transform crawl configs
        crawl_configs = CrawlConfigs.from_database()
        if not list(crawl_configs.scheduled()):
            msg = "No crawl configs with a schedule found in database! No jobs scheduled."
            log.error(msg)
        else:
            scheduler.remove_all_jobs(jobstore="redis", include_pending_jobs=False)
            crawl_jobs = transform_crawl_configs(crawl_configs)
            scheduler.add_jobs(jobs=crawl_jobs, jobstore="redis")

        # Set any pending jobs to run immeidately and clear the pending jobs queue
        scheduler.trigger_pending_jobs()

        # Resume Scheduler and start infinite loop while checking for updates
        scheduler.resume()
    except Exception:
        log.exception("Error initializing scheduler!")

    while wait_for_next_interval(interval=CRAWL_CONFIGS_INTERVAL):
        try:
            # check for updates to crawl configs
            crawl_configs = CrawlConfigs.from_database()
            crawl_jobs = transform_crawl_configs(crawl_configs)

            # Remove jobs that no longer exist in the database
            crawl_job_ids = [crawl_job["id"] for crawl_job in crawl_jobs]
            job_ids_to_remove = [job.id for job in scheduler.get_jobs(jobstore="redis") if job.id not in crawl_job_ids]
            scheduler.remove_jobs(job_ids_to_remove, jobstore="redis")

            # Add new jobs and update existing jobs
            scheduler.add_jobs(crawl_jobs, jobstore="redis", update_existing=True)
        except Exception:
            log.exception("Error updating scheduler!")


def start_scrapy_scheduler(input_file: Path) -> None:
    """Initializes schedule from input file, schedules jobs and runs scheduler"""
    if not input_file.exists():
        msg = f"Cannot start scheduler! Input file {input_file} does not exist."
        raise ValueError(msg)

    # Load and transform crawl configs
    crawl_sites = CrawlConfigs.from_file(file=input_file)
    apscheduler_jobs = transform_crawl_configs(crawl_sites)

    # Initialize Scheduler and add listeners
    scheduler = init_scheduler()
    scheduler.add_listener(scheduler.add_pending_job, EVENT_JOB_SUBMITTED)
    scheduler.add_listener(scheduler.remove_pending_job, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    scheduler.start(paused=True)

    # Remove all jobs from scheduler, and add new version of jobs from config
    scheduler.remove_all_jobs(jobstore="redis", include_pending_jobs=False)
    for apscheduler_job in apscheduler_jobs:
        scheduler.add_job(**apscheduler_job, jobstore="redis")

    # Set any pending jobs to run immeidately and clear the pending jobs queue
    scheduler.trigger_pending_jobs()

    # Resume Scheduler and start infinite loop to keep the scheduler process open
    scheduler.resume()
    keep_scheduler_alive()


if __name__ == "__main__":
    start_scrapy_scheduler(input_file=CRAWL_SITES_FILE)
