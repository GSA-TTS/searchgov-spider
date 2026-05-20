"""Define your item pipelines here
Don't forget to add your pipeline to the ITEM_PIPELINES setting
See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
"""

import contextlib
import os
from pathlib import Path
from typing import Self

import requests
from scrapy.crawler import Crawler
from scrapy.exceptions import DropItem

from search_gov_crawler.indexing.helpers import update_dap_visits_to_document
from search_gov_crawler.indexing.opensearch import SearchGovOpensearch
from search_gov_crawler.indexing.transform import convert_html, convert_pdf
from search_gov_crawler.search_gov_spiders.items import FreshnessSpiderItem, SearchGovSpidersItem


def safe_del(item, key: str):
    """
    This method prevents any exception errors if item does not have the key or is null.
    This is just in case, since the item should always have the keys we delete
    """

    with contextlib.suppress(Exception):
        del item[key]


class SearchGovSpidersPipeline:
    """
    Pipeline that writes items to files for manual upload, or sends batched POST
    requests (both rotated at ~100KB) to SPIDER_URLS_API if the environment variable is set.
    """

    MAX_URL_BATCH_SIZE_BYTES = 100 * 1024  # 100KB in bytes
    APP_PID = os.getpid()

    def __init__(self, *, crawler: Crawler) -> None:
        self.api_url = os.environ.get("SPIDER_URLS_API")
        self.urls_batch = []
        self.file_number = 1
        self.file_path = None
        self.current_file = None
        self.file_open = False
        self._opensearch = None
        self.crawler = crawler
        self.spider_logger = crawler.spider.logger

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        """Supports initialization with Crawler to access spider data."""
        return cls(crawler=crawler)

    def process_item(self, item: SearchGovSpidersItem) -> SearchGovSpidersItem:
        """Handle each item by writing to file or batching URLs for an API POST."""
        url = item.get("url", None)
        output_target = item.get("output_target", None)

        if output_target not in ["endpoint", "opensearch", "csv"]:
            msg = f"Not a valid output_target: {output_target}"
            raise DropItem(msg)

        if not url:
            msg = "Missing URL in item"
            raise DropItem(msg)

        if output_target == "opensearch":
            self._process_opensearch_item(item)
        elif output_target == "endpoint":
            if not self.api_url:
                msg = "Item 'endpoint' not resolved, env.SPIDER_URLS_API is not set"
                raise DropItem(msg)
            self._process_api_item(url)
        else:  # csv
            self._process_file_item(url)

        safe_del(item, "output_target")
        safe_del(item, "response_bytes")
        safe_del(item, "response_language")
        safe_del(item, "content_type")

        return item

    @property
    def opensearch(self) -> SearchGovOpensearch:
        """Lazily initialize the OpenSearch client when first accessed."""

        if not self._opensearch:
            self._opensearch = SearchGovOpensearch()
        return self._opensearch

    def _process_opensearch_item(self, item: SearchGovSpidersItem) -> None:
        doc = {}

        if not item.get("response_bytes"):
            err = f"Missing 'response_bytes' for item: {item}"
            self.spider_logger.error(err)
            raise DropItem(err)

        try:
            match item.get("content_type", None):
                case "text/html":
                    doc = convert_html(item=item)
                case "application/pdf":
                    doc = convert_pdf(item=item)
                case _:
                    self.spider_logger.warning("Unsupported content type for item %s", item)
        except Exception:
            self.spider_logger.exception("Failed to convert item %s", item)

        if not doc:
            self.spider_logger.warning("No document generated for item %s", item)
            return

        try:
            doc = update_dap_visits_to_document(doc, self.crawler.spider)
        except Exception:
            self.spider_logger.exception("Failed to update DAP visits for document %s", doc[id])
            # still continue to include the doc without DAP data

        try:
            self.opensearch.add_to_batch(doc=doc, spider=self.crawler.spider)
        except Exception as exc:
            msg = "Failed to add item to Opensearch batch"
            self.crawler.spider.logger.exception(msg)
            raise DropItem(msg) from exc

    def _process_api_item(self, url: str) -> None:
        """Batch URLs for API and send POST if size limit is reached."""
        self.urls_batch.append(url)
        if self._batch_size() >= self.MAX_URL_BATCH_SIZE_BYTES:
            self._send_post_request()

    def _process_file_item(self, url: str) -> None:
        """Write URL to file and rotate the file if size exceeds the limit."""

        if not self.file_open:
            self.file_open = True
            output_dir = Path(__file__).parent.parent / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            base_filename = f"all-links-p{self.APP_PID}"
            self.file_path = output_dir / f"{base_filename}.csv"
            self.current_file = open(self.file_path, "a", encoding="utf-8")  # noqa: PTH123, SIM115

        self.current_file.write(f"{url}\n")
        if self._file_size() >= self.MAX_URL_BATCH_SIZE_BYTES:
            self._rotate_file()

    def _batch_size(self) -> int:
        """Calculate total size of the batched URLs."""
        return sum(len(url.encode("utf-8")) for url in self.urls_batch)

    def _file_size(self) -> int:
        """Get the current file size."""
        self.current_file.flush()  # Ensure the OS writes buffered data to disk
        return self.file_path.stat().st_size

    def _rotate_file(self) -> None:
        """Close the current file, rename it, and open a new one."""
        self.current_file.close()
        rotated_file = self.file_path.with_name(f"{self.file_path.stem}-{self.file_number}.csv")
        os.rename(self.file_path, rotated_file)  # noqa: PTH104
        self.current_file = open(self.file_path, "a", encoding="utf-8")  # noqa: PTH123, SIM115
        self.file_number += 1

    def _send_post_request(self) -> None:
        """Send a POST request with the batched URLs."""
        try:
            response = requests.post(self.api_url, json={"urls": self.urls_batch}, timeout=60)
            response.raise_for_status()
            self.crawler.spider.logger.info("Successfully posted %s URLs to %s", len(self.urls_batch), {self.api_url})
        except requests.RequestException:
            msg = f"Failed to send URLs to {self.api_url}"
            self.crawler.spider.logger.exception(msg)
            raise DropItem(msg) from None
        finally:
            self.urls_batch.clear()

    def close_spider(self) -> None:
        """Finalize operations: close files or send remaining batched URLs."""
        try:
            if self._opensearch:
                self.opensearch.batch_upload(spider=self.crawler.spider)
        except Exception:
            msg = "Failed to upload Opensearch batch"
            self.crawler.spider.logger.exception(msg)

        if self.urls_batch:
            self._send_post_request()

        if self.current_file:
            self.current_file.close()


class DeDeuplicatorPipeline:
    """Class for pipeline that removes duplicate items"""

    def __init__(self, *, crawler: Crawler) -> None:
        self.urls_seen = set()
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        """Supports initialization with Crawler to access spider data."""
        return cls(crawler=crawler)

    def process_item(self, item):
        """
        If item has already been seen, drop it otherwise add to
        """
        if item["url"] in self.urls_seen:
            msg = "Item already seen!"
            raise DropItem(msg)

        self.urls_seen.add(item["url"])
        return item


class FreshnessSpiderPipeline:
    """Pipeline for the freshness spider to log the status of URLs checked"""

    def __init__(self, *, crawler: Crawler) -> None:
        self.crawler = crawler
        self.opensearch = SearchGovOpensearch(opensearch_index="spider-freshness")
        self.spider_logger = crawler.spider.logger

    def open_spider(self):
        """Create the freshness index if it doesn't exist"""
        # with contextlib.suppress(RequestError):
        if not self.opensearch.index_exists():
            self.opensearch.create_index(template=FreshnessSpiderItem.generate_template())

    def process_item(self, item: FreshnessSpiderItem) -> None:
        """Log the URL and status code from the freshness spider item."""
        self.spider_logger.info("Stale URL found, Result: %s.  URL: %s", item.result, item.path)
        try:
            self.opensearch.add_to_batch(doc=item.to_dict(), spider=self.crawler.spider)
        except Exception as exc:
            msg = "Failed to add item to Opensearch batch"
            self.spider_logger.exception(msg)
            raise DropItem(msg) from exc

    def close_spider(self) -> None:
        """Finalize operations by uploading any remaining items to Opensearch."""

        try:
            self.opensearch.batch_upload(spider=self.crawler.spider)
        except Exception:
            msg = "Failed to upload Opensearch batch on spider close"
            self.spider_logger.exception(msg)

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        """Supports initialization with Crawler to access spider data."""
        return cls(crawler=crawler)
