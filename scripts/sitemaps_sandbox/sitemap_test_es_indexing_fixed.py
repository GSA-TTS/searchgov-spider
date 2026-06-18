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


def force_gc() -> None:
    """
    Forces garbage collection to clean up any remaining objects in memory after a crawl.
    """

    ref_count = gc.collect()
    log.info("Cleaned %s unreachable objects.", ref_count)


def run_crawl_in_dedicated_process(spider_params):
    """
    Runs a crawl in a dedicated process to avoid issues with starting/stopping the twisted reactor in the same process.
    """

    os.environ.setdefault("SPIDER_SPIDERMON_ENABLED", "False")

    settings = get_project_settings()

    process = CrawlerProcess(settings, install_root_handler=False)

    spider_cls = DomainSpider

    process.crawl(spider_cls, **spider_params)
    process.start()
    force_gc()


def do_crawl_sequential(new_urls: list[str]):
    """
    Runs a crawl with the same parameters twice sequentially."""
    spider_kwargs = {
        "allow_query_string": False,
        "allowed_domains": "ioos.noaa.gov",
        "deny_paths": None,
        "start_urls": ",".join(new_urls),
        "output_target": "opensearch",
        "sitemap_url": "https://ioos.noaa.gov/sitemap.xml",
        "depth_limit": 1,
    }

    log.info("Starting crawl with args: %s", spider_kwargs.get("start_urls"))
    crawl_process = Process(target=run_crawl_in_dedicated_process, kwargs=spider_kwargs)
    crawl_process.start()
    crawl_process.join()  # Wait for the crawl process to complete before continuing, force blocking
    log.info("Crawl with args: %s finished.", spider_kwargs.get("start_urls"))


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
    do_crawl_sequential(first_run_urls)
    log.info("First crawl completed.\n")

    log.info("Executing second crawl (same parameters for this example)...")
    second_run_urls = [
        "https://ioos.noaa.gov/about/meet-the-ioos-program-office/",
        "https://ioos.noaa.gov/about/ioos-history/",
    ]
    do_crawl_sequential(second_run_urls)
    log.info("Second crawl completed.")
