"""Define your item pipelines here
Don't forget to add your pipeline to the ITEM_PIPELINES setting
See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
"""

from typing import Self

from scrapy.crawler import Crawler
from scrapy.exceptions import DropItem

from search_gov_crawler.indexing.opensearch import SearchGovOpensearch
from search_gov_crawler.search_gov_spiders.items import FreshnessSpiderItem


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
