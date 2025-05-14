import os
import sys
from dotenv import load_dotenv
from pathlib import Path

import requests
import xml.etree.ElementTree as ET
import time
import logging
from datetime import datetime
from typing import Dict, List, Set, Tuple
import hashlib
import heapq

from pythonjsonlogger.json import JsonFormatter

from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT
from search_gov_crawler.search_gov_spiders.crawl_sites import CrawlSite

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from search_gov_crawler.search_gov_spiders.spiders.domain_spider import DomainSpider
from search_gov_crawler.search_gov_spiders.spiders.domain_spider_js import DomainSpiderJs

from search_gov_crawler.search_gov_spiders.crawl_sites import CrawlSites
from search_gov_crawler.search_gov_spiders.sitemaps.sitemap_finder import SitemapFinder
from search_gov_crawler.scrapy_scheduler import CRAWL_SITES_FILE

load_dotenv()

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("search_gov_crawler.search_gov_spiders.sitemaps")

TARGET_DIR = Path("/var/tmp/spider_sitemaps")

def create_directory(path: Path) -> None:
    """Creates the directory using pathlib if it doesn't exist."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        log.info(f"Directory '{path}' ensured.")
    except OSError as e:
        log.error(f"Error creating directory '{path}': {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        log.error(f"An unexpected error occurred creating directory '{path}': {e}", exc_info=True)
        sys.exit(1)

class SitemapMonitor:
    def __init__(self, records: List[CrawlSite]):
        """Initialize the SitemapMonitor with crawl site records."""
        self.records = records

    def setup(self):
        """Setup and filter records based on depth and sitemap availability."""
        # Filter records to only include those with depth_limit >= 8
        records = self.records
        records = [record for record in records if record.depth_limit >= 8]
        
        sitemap_finder = SitemapFinder()
        records_len = len(records)
        records_count = 0
        for record in records:
            starting_url = record.starting_urls.split(",")[0]
            records_count += 1
            log.info(f"({records_count} of {records_len}) Checking sitemap for: {starting_url}")
            
            # Default check interval is 48 hours if not specified
            record.check_sitemap_hours = (record.check_sitemap_hours or 48) * 3600

            if not sitemap_finder.confirm_sitemap_url(record.sitemap_url):
                if record.sitemap_url:
                    record.sitemap_url = None
                    log.error(f"Failed to get existing record.sitemap_url: {record.sitemap_url} for: {starting_url}")
                log.info(f"Attempting to retrieve sitemap_url for: {starting_url}")
                try:
                    record.sitemap_url = sitemap_finder.find(starting_url)
                    if record.sitemap_url:
                        log.info(f"Found sitemap_url: {record.sitemap_url} for starting_url: {starting_url}")
                    else:
                        log.warning(f"Failed to find sitemap_url for starting_url: {starting_url}")
                except Exception as e:
                    log.warning(f"Failed to find sitemap_url for starting_url: {starting_url}. Reason: {e}")
        records = [record for record in records if record and record.sitemap_url]

        for i, record in enumerate(records):
            if not hasattr(record, 'sitemap_url'):
                log.error(f"Record at index {i} is not a valid object: {record} (type: {type(record)})")
        
        self.records_map = {record.sitemap_url: record for record in records}
        self.records = records
        self.stored_sitemaps: Dict[str, Set[str]] = {}
        self.next_check_times: Dict[str, float] = {}
        self.is_first_run: Dict[str, bool] = {}
        
        # Create data directory if it doesn't exist
        create_directory(TARGET_DIR)
        
        # Load any previously stored sitemaps and set first run status
        self._load_stored_sitemaps()
        
        # Initialize the next check times
        current_time = time.time()
        for record in self.records:
            self.next_check_times[record.sitemap_url] = current_time
    
    def _load_stored_sitemaps(self) -> None:
        """Load previously stored sitemaps from disk if they exist and set first run status."""
        for record in self.records:
            url_hash = hashlib.md5(record.sitemap_url.encode()).hexdigest()
            file_path = TARGET_DIR / f"{url_hash}.txt"
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r") as f:
                        urls = set(line.strip() for line in f.readlines())
                        self.stored_sitemaps[record.sitemap_url] = urls
                        log.info(f"Loaded {len(urls)} URLs from stored sitemap for {record.sitemap_url}")
                except Exception as e:
                    log.error(f"Error loading stored sitemap for {record.sitemap_url}: {e}")
                    self.stored_sitemaps[record.sitemap_url] = set()
                self.is_first_run[record.sitemap_url] = False
            else:
                self.stored_sitemaps[record.sitemap_url] = set()
                self.is_first_run[record.sitemap_url] = True
                
    def _save_sitemap(self, sitemap_url: str, urls: Set[str]) -> None:
        """Save sitemap URLs to disk."""
        url_hash = hashlib.md5(sitemap_url.encode()).hexdigest()
        file_path = TARGET_DIR / f"{url_hash}.txt"
        
        try:
            with open(file_path, "w") as f:
                for url in sorted(urls):
                    f.write(f"{url}\n")
            log.info(f"Saved {len(urls)} URLs for {sitemap_url}")
        except Exception as e:
            log.error(f"Error saving sitemap for {sitemap_url}: {e}")
    
    def _fetch_sitemap(self, url: str, depth: int = 0, max_depth: int = 10) -> Set[str]:
        """
        Fetch and parse a sitemap XML file recursively up to a maximum depth.
        
        Args:
            url: The URL of the sitemap to fetch
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops
            
        Returns:
            A set of URLs found in the sitemap
        """
        if depth > max_depth:
            log.error(f"Maximum recursion depth ({max_depth}) exceeded for sitemap {url}")
            return set()

        try:
            log.info(f"Fetching sitemap from {url} at depth {depth}")
            with requests.Session() as session:
                session.headers.update({"Cache-Control": "no-cache"})
                session.cache_disabled = True
                response = session.get(url, timeout=30)
            
                # Parse the XML
                root = ET.fromstring(response.content)
                
                urls = set()
                ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
                
                if root.tag.endswith("sitemapindex"):
                    for sitemap in root.findall(f"{ns}sitemap"):
                        loc = sitemap.find(f"{ns}loc")
                        if loc is not None and loc.text:
                            child_urls = self._fetch_sitemap(loc.text, depth + 1, max_depth)
                            urls.update(child_urls)
                else:
                    for url_element in root.findall(f"{ns}url"):
                        loc = url_element.find(f"{ns}loc")
                        if loc is not None and loc.text:
                            urls.add(loc.text)
                
                log.info(f"Found {len(urls)} URLs in sitemap {url}")
                return urls
            
        except requests.exceptions.RequestException as e:
            log.error(f"Error fetching sitemap {url}: {e}")
            return set()
        except ET.ParseError as e:
            log.error(f"Error parsing sitemap XML from {url}: {e}")
            return set()
        except Exception as e:
            log.error(f"Unexpected error processing sitemap {url}: {e}")
            return set()
    
    def _check_for_changes(self, sitemap_url: str) -> Tuple[Set[str], int]:
        """
        Check a sitemap for new URLs, only storing on first run.
        
        Args:
            sitemap_url: The URL of the sitemap to check
            
        Returns:
            Tuple of (new URLs, total URLs count)
        """
        try:
            if sitemap_url in self.is_first_run and self.is_first_run[sitemap_url]:
                current_urls = self._fetch_sitemap(sitemap_url)
                self.stored_sitemaps[sitemap_url] = current_urls
                self._save_sitemap(sitemap_url, current_urls)
                self.is_first_run[sitemap_url] = False
                log.info(f"First run for {sitemap_url}: stored {len(current_urls)} URLs without indexing")
                return set(), len(current_urls)
            else:
                current_urls = self._fetch_sitemap(sitemap_url)
                previous_urls = self.stored_sitemaps.get(sitemap_url, set())
                new_urls = current_urls - previous_urls
                self.stored_sitemaps[sitemap_url] = current_urls
                self._save_sitemap(sitemap_url, current_urls)
                return new_urls, len(current_urls)
        except Exception as e:
            log.error(f"Error checking for changes in {sitemap_url}: {e}")
            return set(), 0
    
    def _get_check_interval(self, url: str) -> int:
        """Get the check interval for a specific URL in seconds."""
        for record in self.records:
            if record.sitemap_url == url:
                return record.check_sitemap_hours
        return 86400  # Default to 24 hours
    
    def run(self) -> None:
        """Run the sitemap monitor continuously."""
        self.setup()
        log.info(f"Starting Sitemap Monitor for {len(self.records)} sitemaps")
        
        for record in self.records:
            hours = record.check_sitemap_hours / 3600
            log.info(f"Check interval for {record.sitemap_url}: {hours:.1f} hours")
        
        check_queue = []
        for record in self.records:
            heapq.heappush(check_queue, (self.next_check_times[record.sitemap_url], record.sitemap_url))
        
        try:
            while True:
                if not check_queue:
                    log.error("Check queue is empty. This shouldn't happen.")
                    break
                
                next_check_time, sitemap_url = heapq.heappop(check_queue)
                current_time = time.time()
                sleep_time = max(0, next_check_time - current_time)
                
                if sleep_time > 0:
                    next_check_str = datetime.fromtimestamp(next_check_time).strftime("%Y-%m-%d %H:%M:%S")
                    log.info(f"Waiting until {next_check_str} to check {sitemap_url} (sleeping for {sleep_time:.1f} seconds)")
                    time.sleep(sleep_time)
                
                log.info(f"Processing sitemap: {sitemap_url}")
                new_urls, total_count = self._check_for_changes(sitemap_url)
                
                if new_urls:
                    log.info(f"Found {len(new_urls)} new URLs in {sitemap_url}")
                    log.info("New URLs:")
                    for url in sorted(new_urls):
                        log.info(f"  - {url}")
                    
                    record = self.records_map[sitemap_url]
                    spider_args = {
                        "allow_query_string": record.allow_query_string,
                        "allowed_domains": record.allowed_domains,
                        "deny_paths": record.deny_paths,
                        "start_urls": ",".join(new_urls),
                        "output_target": record.output_target,
                        "prevent_follow": True,
                        "depth_limit": 1,
                    }
                    spider_cls = DomainSpiderJs if record.handle_javascript else DomainSpider
                    process = CrawlerProcess(get_project_settings(), install_root_handler=False)
                    process.crawl(spider_cls, **spider_args)
                    process.start()
                else:
                    log.info(f"No new URLs found in {sitemap_url}")
                
                log.info(f"Total URLs in sitemap: {total_count}")
                
                check_interval = self._get_check_interval(sitemap_url)
                self.next_check_times[sitemap_url] = time.time() + check_interval
                next_check_str = datetime.fromtimestamp(self.next_check_times[sitemap_url]).strftime("%Y-%m-%d %H:%M:%S")
                log.info(f"Next check for {sitemap_url} scheduled at {next_check_str}")
                
                heapq.heappush(check_queue, (self.next_check_times[sitemap_url], sitemap_url))
                
        except KeyboardInterrupt:
            log.info("Sitemap Monitor stopped by user")
        except Exception as e:
            log.error(f"Sitemap Monitor stopped due to error: {e}")
            raise
