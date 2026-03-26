import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from pythonjsonlogger.json import JsonFormatter

from search_gov_crawler.search_gov_app.crawl_config import CrawlConfigs
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT
from search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor import SitemapMonitor

load_dotenv()

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("search_gov_crawler.run_sitemap_monitor")

CRAWL_SITES_FILE = (
    Path(__file__).parent / "domains" / os.environ.get("SPIDER_CRAWL_SITES_FILE_NAME", "crawl-sites-production.json")
)


def start_sitemap_monitor(input_file: Path) -> None:
    """Initializes and runs the sitemap monitor from an input file."""
    if not input_file.exists():
        msg = f"Cannot start sitemap monitor! Input file {input_file} does not exist."
        raise FileNotFoundError(msg)

    log.info("Starting Sitemap Monitor with input file: %s", input_file)
    try:
        records = CrawlConfigs.from_file(file=input_file)
        monitor = SitemapMonitor(records.root)
        monitor.run()
    except Exception:
        log.exception("Fatal error in Sitemap Monitor")
        raise


if __name__ == "__main__":
    start_sitemap_monitor(input_file=CRAWL_SITES_FILE)
