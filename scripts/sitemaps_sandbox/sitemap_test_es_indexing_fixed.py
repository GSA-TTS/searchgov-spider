import gc
import logging
import os
from multiprocessing import Process

from dotenv import load_dotenv
from pythonjsonlogger.json import JsonFormatter
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT
from search_gov_crawler.search_gov_spiders.spiders.domain_spider import DomainSpider

# This fixes the double logging issue.
# The problem was getLogger always gets/creates a new instance of logging

log = logging.getLogger("search_gov_crawler.search_gov_spiders.sitemaps")
if not log.hasHandlers():
    log_level_str = os.environ.get("SCRAPY_LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    log.setLevel(log_level)
    log.addHandler(logging.StreamHandler())
    log.handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log.propagate = False

load_dotenv()


# Solution was to run each crawl in a separate process.
# Each process will have its own independent twisted reactor, avoiding the stop/start conflict


def force_gc():
    ref_count = gc.collect()
    log.info(f"Cleaned {ref_count} unreachable objects.")


def run_crawl_in_dedicated_process(spider_params):
    os.environ.setdefault("SPIDER_SPIDERMON_ENABLED", "False")

    settings = get_project_settings()

    process = CrawlerProcess(settings, install_root_handler=False)

    spider_cls = DomainSpider

    process.crawl(spider_cls, **spider_params)
    process.start()
    force_gc()


def doCrawl_sequential(new_urls: list[str]):

    spider_args = {
        "allow_query_string": False,
        "allowed_domains": "ioos.noaa.gov",
        "deny_paths": None,
        "start_urls": ",".join(new_urls),
        "output_target": "opensearch",
        "prevent_follow": True,
        "depth_limit": 1,
    }

    log.info(f"Starting crawl with args: {spider_args.get('start_urls')}")
    crawl_process = Process(target=run_crawl_in_dedicated_process, args=(spider_args,))
    crawl_process.start()
    crawl_process.join()  # Wait for the crawl process to complete before continuing, force blocking
    log.info(f"Crawl with args: {spider_args.get('start_urls')} finished.")


if __name__ == "__main__":
    """
    NOTE: Even though there are 4 URLs total, it will only create 3
    unique documetns one url is a duplicate
    """
    log.info("Executing first crawl...")
    first_run_urls = [
        "https://ioos.noaa.gov/project/ocean-enterprise-study/",
        "https://ioos.noaa.gov/about/ioos-history/",
    ]
    doCrawl_sequential(first_run_urls)
    log.info("First crawl completed.\n")

    log.info("Executing second crawl (same parameters for this example)...")
    second_run_urls = [
        "https://ioos.noaa.gov/about/meet-the-ioos-program-office/",
        "https://ioos.noaa.gov/about/ioos-history/",
    ]
    doCrawl_sequential(second_run_urls)
    log.info("Second crawl completed.")
