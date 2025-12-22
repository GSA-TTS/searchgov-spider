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

if __name__ == "__main__":
    log.info("Starting Sitemap Monitor...")
    records = CrawlConfigs.from_file(file=CRAWL_SITES_FILE)
    monitor = SitemapMonitor(records.root)
    monitor.run()
