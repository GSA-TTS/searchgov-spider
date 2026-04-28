import logging
import os
from pathlib import Path

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from search_gov_crawler.config.freshness import FRESHNESS_CHECKER_CONFIG_FILE
from search_gov_crawler.config.freshness.freshness_config import FreshnessCheckerConfigs
from search_gov_crawler.run.crawl import run_scrapy_crawl
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT, JsonFormatter

load_dotenv()

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("search_gov_crawler.dap_extractor")


def init_scheduler() -> BlockingScheduler:
    """Initialize in memory scheduler with capacity to run a single job at a time."""

    return BlockingScheduler(
        jobstores={"default": MemoryJobStore()},
        executors={"default": ThreadPoolExecutor(max_workers=1)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": None},
        timezone="UTC",
    )


def check_freshness(input_file: Path) -> None:
    """Main function, handles getting the schedule and starting the scheduler for the freshness checker spider"""

    if not input_file.exists():
        msg = f"Cannot start freshness checker! Input file {input_file} does not exist."
        raise ValueError(msg)

    freshness_checker_configs = FreshnessCheckerConfigs.from_file(file=input_file)

    scheduler = init_scheduler()
    for spider_config in freshness_checker_configs:
        try:
            cron_trigger = CronTrigger.from_crontab(spider_config.schedule)
        except (AttributeError, TypeError, ValueError):
            log.exception("Invalid crontab expression from in Freshness Checker Config!")
            raise

        scheduler.add_job(
            func=run_scrapy_crawl,
            trigger=cron_trigger,
            kwargs={
                "spider": "freshness_spider",
                "query": spider_config.query,
                "max_results": spider_config.max_results,
            },
            name=spider_config.name,
        )

    scheduler.start()


if __name__ == "__main__":
    check_freshness(input_file=FRESHNESS_CHECKER_CONFIG_FILE)
