"""
Starts scrapy scheduler.  Takes job details from the crawl-sites-production.json file referenced below as
CRAWL_SITES_FILE. Schedule is fully contained in-memory but current cron expression is stored in the input file
so that on each deploy the schedule can pickup where it left off.

Use the env var SPIDER_SCRAPY_MAX_WORKERS to control how many jobs can run at once.  If the max number of
jobs are running when other jobs are supposed to run, those jobs will queue until one or more of the running
jobs finishes.
"""

import logging
import os
import subprocess
from pathlib import Path

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from pythonjsonlogger.json import JsonFormatter

from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT
from search_gov_crawler.search_gov_spiders.utility_files.crawl_sites import CrawlSites
from search_gov_crawler.elasticsearch.es_batch_upload import SearchGovElasticsearch

load_dotenv()

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("search_gov_crawler.scrapy_scheduler")

CRAWL_SITES_FILE = (
    Path(__file__).parent
    / "search_gov_spiders"
    / "utility_files"
    / os.environ.get("SPIDER_CRAWL_SITES_FILE_NAME", "crawl-sites-production.json")
)


def run_scrapy_crawl(
    spider: str, allow_query_string: bool, allowed_domains: str, start_urls: str, output_target: str
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
    )

    subprocess.run(cmd, check=True, cwd=Path(__file__).parent, env=scrapy_env, executable="/bin/bash", shell=True)
    msg = (
        "Successfully completed scrapy crawl with args "
        "spider=%s, allow_query_string=%s, allowed_domains=%s, start_urls=%s, output_target=%s"
    )
    log.info(msg, spider, allow_query_string, allowed_domains, start_urls, output_target)


def transform_crawl_sites(crawl_sites: CrawlSites) -> list[dict]:
    """
    Transform crawl sites records into a format that can be used to create apscheduler jobs.  Only
    scheduler jobs that have a value for the `schedule` field.
    """

    transformed_crawl_sites = []

    for crawl_site in crawl_sites.scheduled():
        job_name = crawl_site.name
        transformed_crawl_sites.append(
            {
                "func": run_scrapy_crawl,
                "id": job_name.lower().replace(" ", "-").replace("---", "-"),
                "name": job_name,
                "trigger": CronTrigger.from_crontab(expr=crawl_site.schedule, timezone="UTC"),
                "args": [
                    "domain_spider" if not crawl_site.handle_javascript else "domain_spider_js",
                    crawl_site.allow_query_string,
                    crawl_site.allowed_domains,
                    crawl_site.starting_urls,
                    crawl_site.output_target,
                ],
            },
        )

    return transformed_crawl_sites


def init_scheduler() -> BlockingScheduler:
    """
    Create and return instance of scheduler.  Set `max_workers`, i.e. the maximum number of spider
    processes this scheduler will spawn at one time to either the value of an environment variable
    or the default value from pythons concurrent.futures ThreadPoolExecutor.
    """

    # Initalize scheduler - 'min(32, (os.cpu_count() or 1) + 4)' is default from concurrent.futures
    # but set to default of 5 to ensure consistent numbers between environments and for schedule
    max_workers = int(os.environ.get("SPIDER_SCRAPY_MAX_WORKERS", "5"))
    log.info("Max workers for schedule set to %s", max_workers)

    return BlockingScheduler(
        jobstores={"memory": MemoryJobStore()},
        executors={"default": ThreadPoolExecutor(max_workers)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": None},
        timezone="UTC",
    )


def start_scrapy_scheduler(input_file: Path) -> None:
    """Initializes schedule from input file, schedules jobs and runs scheduler"""
    if isinstance(input_file, str):
        input_file = Path(input_file)
    # Load and transform crawl sites
    crawl_sites = CrawlSites.from_file(file=input_file)
    apscheduler_jobs = transform_crawl_sites(crawl_sites)

    # Schedule Jobs
    scheduler = init_scheduler()
    for apscheduler_job in apscheduler_jobs:
        scheduler.add_job(**apscheduler_job, jobstore="memory")

    es = SearchGovElasticsearch()
    es.create_index_if_not_exists()
    # Run Scheduler
    scheduler.start()


if __name__ == "__main__":
    start_scrapy_scheduler(input_file=CRAWL_SITES_FILE)
