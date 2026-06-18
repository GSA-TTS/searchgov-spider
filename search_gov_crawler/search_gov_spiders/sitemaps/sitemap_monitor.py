import gc
import hashlib
import heapq
import itertools
import logging
import os
import sys
import time
from datetime import UTC, datetime
from multiprocessing import Process
from pathlib import Path
from typing import Any

import requests
from defusedxml.ElementTree import ParseError, fromstring
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from search_gov_crawler.search_gov_app.crawl_config import CrawlConfig
from search_gov_crawler.search_gov_spiders.job_state.scheduler import disable_redis_job_state
from search_gov_crawler.search_gov_spiders.settings.common import USER_AGENT
from search_gov_crawler.search_gov_spiders.sitemaps.sitemap_finder import SitemapFinder
from search_gov_crawler.search_gov_spiders.spiders import SpiderStartedBy
from search_gov_crawler.search_gov_spiders.spiders.domain_spider import DomainSpider
from search_gov_crawler.search_gov_spiders.spiders.domain_spider_js import DomainSpiderJs

log = logging.getLogger(__name__)


TARGET_DIR = Path("/var/tmp/spider_sitemaps")  # noqa: S108


def create_directory(path: Path) -> None:
    """Creates the directory using pathlib if it doesn't exist."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        log.info("Directory '%s' ensured.", path)
    except OSError:
        log.exception("Error creating directory '%s'", path)
        sys.exit(1)
    except Exception:
        log.exception("An unexpected error occurred creating directory '%s'", path)
        sys.exit(1)


def force_gc() -> None:
    """Forces garbage collection, as a saftey measure."""
    ref_count = gc.collect()
    log.info("Cleaned %s unreachable objects.", ref_count)


def run_crawl_in_dedicated_process(spider_cls: type[DomainSpiderJs] | type[DomainSpider], spider_args: dict[str, Any]):
    """Runs a Scrapy spider in a new, dedicated process.

    Initializes a scrapy CrawlerProcess with our project settings,
    disables Spidermon by default for this specific updating crawl.
    Forces garbage collection after the process has finished to de-ref
    leftover objects

    Args:
        spider_cls: The Scrapy spider class (e.g., DomainSpiderJs or DomainSpider)
            to be run.
        spider_args: A dictionary containing the arguments to be passed
            to the spider during initialization.
    """
    os.environ.setdefault("SPIDER_SPIDERMON_ENABLED", "False")
    settings = get_project_settings()
    settings = disable_redis_job_state(settings)

    process = CrawlerProcess(settings, install_root_handler=False)
    process.crawl(spider_cls, **spider_args)
    process.start()
    force_gc()


class SitemapMonitor:
    """
    Class that runs the sitemap monitor.
    """

    def __init__(self, records: list[CrawlConfig]):
        """Initialize the SitemapMonitor with crawl site records."""
        self.records = records
        self.all_sitemap_urls: list[str] = []
        self.records_map: dict[str, CrawlConfig] = {}
        self.stored_sitemaps: dict[str, set[str]] = {}
        self.next_check_times: dict[str, float] = {}
        self.is_first_run: dict[str, bool] = {}

    def _process_record_sitemaps(self, record: CrawlConfig, sitemap_finder: SitemapFinder) -> list[str]:
        """
        Validates predefined sitemaps, discovers new ones, and returns a combined list
        of unique, valid sitemap URLs for the given record.
        """

        starting_url = (record.starting_urls or "").split(",")[0]

        # Step 1: Handle predefined sitemaps
        predefined_sitemaps: set[str] = set()

        for url in record.sitemap_urls or []:
            if sitemap_finder.confirm_sitemap_url(url):
                log.info("Confirmed predefined sitemap URL %s for %s", url, starting_url)
                predefined_sitemaps.add(url)
            else:
                log.warning("Could not confirm predefined sitemap URL %s for %s", url, starting_url)

        # Step 2: Discover new sitemaps
        found_sitemaps: set[str] = set()

        try:
            found_sitemaps = sitemap_finder.find(starting_url)
            if not found_sitemaps:
                msg = "no sitemap URLs found"
                raise Exception(msg)  # noqa: TRY301
            log.info("Discovered sitemap URLs: %s for %s", list(found_sitemaps), starting_url)
        except Exception as e:
            log.warning("Failed to discover sitemaps for %s. Reason: %s", starting_url, e)

        # Step 3: Combine and return both found_sitemaps and predefined_sitemaps
        return list(predefined_sitemaps | found_sitemaps)

    def setup(self):
        """Setup and filter records, then find and validate all sitemap URLs."""
        sitemap_finder = SitemapFinder()
        all_sitemaps_set: set[str] = set()

        # Step 1: Filter records and process sitemaps for each one
        records_to_process = [r for r in self.records if r.depth_limit >= 8]  # noqa: PLR2004

        for record in records_to_process:
            # Set check interval, defaulting to 48 hours (in seconds)
            record.check_sitemap_hours = (record.check_sitemap_hours or 48) * 3600

            # Find or validate sitemaps for the current record
            valid_sitemaps_for_record = self._process_record_sitemaps(record, sitemap_finder)
            record.sitemap_urls = valid_sitemaps_for_record

            # Add the valid sitemaps to our master set and create a mapping
            for sitemap_url in record.sitemap_urls:
                all_sitemaps_set.add(sitemap_url)
                self.records_map[sitemap_url] = record

        # Step 2: Finalize the list of unique, non-empty sitemap URLs
        all_sitemaps_set.discard("")
        all_sitemaps_set.discard(None)
        self.all_sitemap_urls = list(all_sitemaps_set)

        if not self.all_sitemap_urls:
            log.error("No valid sitemap URLs found after processing all records.")
            sys.exit(1)
        # Create data directory if it doesn't exist
        create_directory(TARGET_DIR)

        # Load any previously stored sitemaps and set first run status
        self._load_stored_sitemaps()

        # Initialize the next check times for all valid sitemaps
        current_time = time.time()
        for sitemap_url in self.all_sitemap_urls:
            self.next_check_times[sitemap_url] = current_time

    def _load_stored_sitemaps(self) -> None:
        """Load previously stored sitemaps from disk if they exist and set first run status."""
        for sitemap_url in self.all_sitemap_urls:
            url_hash = hashlib.md5(sitemap_url.encode()).hexdigest()
            file_path = TARGET_DIR / f"{url_hash}.txt"
            if file_path.exists():
                with file_path.open() as f:
                    lines = {ln.strip() for ln in f}
                self.stored_sitemaps[sitemap_url] = lines
                self.is_first_run[sitemap_url] = False
                log.info("Loaded %s URLs from %s", len(lines), sitemap_url)
            else:
                self.stored_sitemaps[sitemap_url] = set()
                self.is_first_run[sitemap_url] = True

    def _save_sitemap(self, sitemap_url: str, urls: set[str]) -> None:
        """Save sitemap URLs to disk."""
        if not urls:
            return

        url_hash = hashlib.md5(sitemap_url.encode()).hexdigest()
        file_path = TARGET_DIR / f"{url_hash}.txt"

        try:
            with file_path.open("w") as f:
                for url in sorted(urls):
                    f.write(f"{url}\n")
            log.info("Saved %s URLs for %s", len(urls), sitemap_url)
        except Exception:
            log.exception("Error saving sitemap for %s", sitemap_url)

    def _fetch_sitemap(self, url: str, depth: int = 0, max_depth: int = 10) -> set[str]:  # noqa: C901
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
            log.error("Maximum recursion depth (%s) exceeded for sitemap %s", max_depth, url)
            return set()

        try:
            urls = set()
            log.info("Fetching sitemap from %s at depth %s", url, depth)
            with requests.Session() as session:
                session.headers.update(
                    {
                        "User-Agent": USER_AGENT,
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    },
                )
                response = session.get(url, timeout=30)
                response.raise_for_status()

                root = fromstring(response.content)
                ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""

                if root.tag.endswith("sitemapindex"):
                    for sitemap in root.findall(f"{ns}sitemap"):
                        loc = sitemap.find(f"{ns}loc")
                        if loc is not None and loc.text:
                            loc_text = loc.text.strip().lower()

                            # Heuristic: treat only likely sitemap URLs as sitemaps
                            if loc_text.endswith(".xml") or "sitemap" in loc_text.lower():
                                child_urls = self._fetch_sitemap(loc_text, depth + 1, max_depth)
                                urls.update(child_urls)
                            else:
                                log.warning("Skipping non-sitemap URL in sitemapindex: %s", loc_text)
                elif root.tag.endswith("urlset"):
                    for url_element in root.findall(f"{ns}url"):
                        loc = url_element.find(f"{ns}loc")
                        if loc is not None and loc.text:
                            urls.add(loc.text.strip())
                else:
                    log.warning("Unrecognized root tag in sitemap XML: %s", root.tag)

                log.info("Found %s URLs in sitemap %s", len(urls), url)
                return urls

        except requests.exceptions.RequestException:
            log.exception("Error fetching sitemap %s", url)
        except ParseError:
            log.exception("Error parsing sitemap XML from %s", url)
        except Exception:
            log.exception("Unexpected error processing sitemap %s", url)

        return urls

    def _check_for_changes(self, sitemap_url: str) -> tuple[set[str], int]:
        """
        Check a sitemap for new URLs, only storing on first run.

        Args:
            sitemap_url: The URL of the sitemap to check

        Returns:
            tuple of (new URLs, total URLs count)
        """
        new_urls = set()
        total_count = 0
        try:
            if self.is_first_run.get(sitemap_url):
                current_urls = self._fetch_sitemap(sitemap_url)
                self.stored_sitemaps[sitemap_url] = current_urls
                self._save_sitemap(sitemap_url, current_urls)
                self.is_first_run[sitemap_url] = False
                total_count = len(current_urls)
                log.info("First run for %s: stored %s URLs without indexing", sitemap_url, total_count)
            else:
                current_urls = self._fetch_sitemap(sitemap_url)
                previous_urls = self.stored_sitemaps.get(sitemap_url, set())
                new_urls = current_urls - previous_urls
                self.stored_sitemaps[sitemap_url] = current_urls
                self._save_sitemap(sitemap_url, current_urls)
                total_count = len(current_urls)
        except Exception:
            log.exception("Error checking for changes in %s", sitemap_url)

        return new_urls, total_count

    def _get_check_interval(self, url: str) -> int:
        """Get the check interval for a specific sitemap URL."""
        record = self.records_map.get(url)
        return getattr(record, "check_sitemap_hours", 24 * 3600)

    def run(self) -> None:
        """Run the sitemap monitor continuously."""
        self.setup()
        log.info("Starting Sitemap Monitor for %s sitemaps", len(self.records))

        check_queue: list[tuple[float, str]] = []
        for sitemap_url in self.all_sitemap_urls:
            interval = f"{self._get_check_interval(sitemap_url) / 3600:.1f}h"
            log.info("Check interval for : %s, %s", sitemap_url, interval)
            heapq.heappush(check_queue, (self.next_check_times[sitemap_url], sitemap_url))

        try:
            while True:
                next_check_time, sitemap_url = heapq.heappop(check_queue)
                current_time = time.time()
                sleep_time = max(0, next_check_time - current_time)

                if sleep_time > 0:
                    next_check_str = datetime.fromtimestamp(next_check_time, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
                    sleep_seconds = f"{sleep_time:.1f} seconds"
                    log.info(
                        "Waiting until %s to check %s (sleeping for %s)",
                        next_check_str,
                        sitemap_url,
                        sleep_seconds,
                    )
                    time.sleep(sleep_time)

                log.info("Processing sitemap: %s", sitemap_url)
                new_urls, total_count = self._check_for_changes(sitemap_url)
                if new_urls:
                    log.info("Found %s new URLs in %s", len(new_urls), sitemap_url)
                    new_urls_msg_lines = ["New URLs:"]
                    new_urls_msg_lines.extend([f"  - {url}" for url in sorted(new_urls)])
                    log.info("\n".join(new_urls_msg_lines))
                    record = self.records_map[sitemap_url]
                    spider_cls = DomainSpiderJs if record.handle_javascript else DomainSpider
                    for url_batch in itertools.batched(sorted(new_urls), 20):
                        spider_args = {
                            "allow_query_string": record.allow_query_string,
                            "allowed_domains": record.allowed_domains,
                            "deny_paths": record.deny_paths,
                            "start_urls": ",".join(url_batch),
                            "output_target": record.output_target,
                            "sitemap_url": sitemap_url,
                            "depth_limit": 1,
                            "started_by": SpiderStartedBy.SITEMAP_DELTA.value,
                        }
                        crawl_process = Process(
                            target=run_crawl_in_dedicated_process,
                            args=(spider_cls, spider_args),
                        )
                        crawl_process.start()
                        # Wait for the crawl process to complete before continuing, forces blocking
                        crawl_process.join()
                        time.sleep(3)
                else:
                    log.info("No changes in %s", sitemap_url)

                log.info("Total URLs in sitemap: %s", total_count)

                check_interval = self._get_check_interval(sitemap_url)
                self.next_check_times[sitemap_url] = time.time() + check_interval
                next_check_str = datetime.fromtimestamp(self.next_check_times[sitemap_url], tz=UTC).strftime(
                    "%Y-%m-%d %H:%M:%S",
                )
                log.info("Next check for %s scheduled at %s", sitemap_url, next_check_str)

                heapq.heappush(check_queue, (self.next_check_times[sitemap_url], sitemap_url))

        except KeyboardInterrupt:
            log.info("Sitemap Monitor stopped by user")
        except Exception:
            log.exception("Sitemap Monitor stopped due to error")
            raise
