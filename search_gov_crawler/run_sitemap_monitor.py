import logging
import os

from dotenv import load_dotenv
from pythonjsonlogger.json import JsonFormatter

from search_gov_crawler.scrapy_scheduler import CRAWL_SITES_FILE
from search_gov_crawler.search_gov_spiders.crawl_sites import CrawlSites
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT
from search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor import SitemapMonitor

load_dotenv()

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("search_gov_crawler.run_sitemap_monitor")

if __name__ == "__main__":
    log.info("Starting Sitemap Monitor...")
    records = CrawlSites.from_file(file=CRAWL_SITES_FILE)
    monitor = SitemapMonitor(records)
    monitor.run()
