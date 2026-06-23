from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import ClassVar

from scrapy import Request, Spider
from scrapy.crawler import Crawler
from scrapy.exceptions import DontCloseSpider
from scrapy.http.response import Response
from scrapy.settings import BaseSettings
from scrapy.signals import spider_idle

from search_gov_crawler.indexing.opensearch import SearchGovOpensearch
from search_gov_crawler.search_gov_spiders.helpers.freshness_spider import (
    count_matching_documents,
    ensure_valid_query,
    get_matching_documents,
)
from search_gov_crawler.search_gov_spiders.items import (
    FreshnessSpiderException,
    FreshnessSpiderExceptionItem,
    FreshnessSpiderMarkedForDeletionItem,
    FreshnessSpiderNotMarkedForDeletionItem,
)


class FreshnessSpider(Spider):
    """Spider used to check URLs from documents in opensearch to determine if they still exist."""

    name = "freshness_spider"
    opensearch: SearchGovOpensearch
    query: dict
    max_results: int | None

    source_documents: Generator[dict, None, None] | None
    doc_count: int
    doc_batch_size: ClassVar[int] = 250

    scroll: ClassVar[str] = "24h"
    status_codes_to_ignore: ClassVar[set[int]] = {200}
    status_codes_to_mark_for_deletion: ClassVar[set[int]] = {
        code.value for code in HTTPStatus if code.is_redirection or code == HTTPStatus.NOT_FOUND
    }

    def __init__(self, *args, query: str, max_results: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.opensearch = SearchGovOpensearch()
        self.query = ensure_valid_query(opensearch=self.opensearch, query=query)
        self.max_results = int(max_results) if max_results else None
        self.doc_count = 0
        self.source_documents = None

    async def start(self) -> AsyncGenerator:
        """
        Generates list of URLs from opensearch to send into the freshness spider.
        """
        matching_documents = count_matching_documents(opensearch=self.opensearch, query=self.query)
        if not matching_documents:
            self.logger.info("No documents found matching query")
            return
            yield  # this is needed to make this an async generator, even though we have nothing to yield in this case
        else:
            self.logger.info("Found %d documents matching query", matching_documents)
            self.source_documents = get_matching_documents(
                opensearch=self.opensearch, query=self.query, scroll=self.scroll
            )
            # Yield the first batch requests
            for request in self._next_batch():
                yield request

    def _next_batch(self) -> Generator[Request, None, None]:
        """
        Private method to get batches of documents from opensearch based on doc_batch_size.
        """

        if not self.source_documents:
            return

        try:
            for doc_in_batch, document in enumerate(self.source_documents, start=1):
                if self.max_results and self.doc_count >= self.max_results:
                    self.logger.info("Reached max query results of %d. Stopping generation of URLs.", self.max_results)
                    self.source_documents.close()
                    break
                try:
                    document_id = document["_id"]
                    document_path = document["_source"]["path"]
                    domain_name = document["_source"]["domain_name"]
                except KeyError as err:
                    msg = f"""
                        Invalid Document:
                        _id = {document.get("_id", "missing_id")}
                        path = {document.get("_source", {}).get("path", "missing_path")}
                        """
                    raise ValueError(msg) from err

                yield Request(
                    document_path, method="HEAD", meta={"document_id": document_id, "domain_name": domain_name}
                )
                self.doc_count += 1

                if doc_in_batch >= self.doc_batch_size:
                    break

        except Exception:
            self.logger.exception("Error while getting OpenSearch documents.")
            self.source_documents.close()
            raise

    def crawl_next_batch(self):
        """ """
        if self.source_documents:
            self.logger.info("Fetching next batch of %s URLs...", self.doc_batch_size)
            requests_added = 0
            for request in self._next_batch():
                # Manually inject the next batch into the engine
                self.crawler.engine.crawl(request)
                requests_added += 1

            if requests_added > 0:
                # Signal Scrapy NOT to close yet
                raise DontCloseSpider

    def parse(self, response: Response):
        """
        Transform the response from URL check into an item to be processed by the pipeline.
        If the URL was not found or returned an invalid status code, create an item with that information.
        Otherwise, ignore the response since we only care about URLs that are not valid.
        """
        if exception := response.meta.get("exception"):
            item = FreshnessSpiderExceptionItem(
                checked_at=datetime.now(tz=UTC),
                result=exception.__class__.__name__,
                status_code=None,
                index_name=self.opensearch.index_name,
                id=response.meta["document_id"],
                path=response.url,
                domain_name=response.meta["domain_name"],
                exception=FreshnessSpiderException(
                    exception_type=exception.__class__.__name__,
                    exception_message=str(exception),
                ),
            )
        elif response.status in self.status_codes_to_ignore:
            self.logger.debug(
                "Ignoring %s response from %s since it does not indicate a failure.",
                response.status,
                response.url,
            )
            return
        elif response.status in self.status_codes_to_mark_for_deletion:
            item = FreshnessSpiderMarkedForDeletionItem(
                checked_at=datetime.now(tz=UTC),
                status_code=str(response.status),
                index_name=self.opensearch.index_name,
                id=response.meta["document_id"],
                path=response.url,
                domain_name=response.meta["domain_name"],
                exception=None,
                result=str(response.status),
            )
        else:
            item = FreshnessSpiderNotMarkedForDeletionItem(
                checked_at=datetime.now(tz=UTC),
                status_code=str(response.status),
                index_name=self.opensearch.index_name,
                id=response.meta["document_id"],
                path=response.url,
                domain_name=response.meta["domain_name"],
                exception=None,
                result=str(response.status),
            )

        yield item

    @classmethod
    def from_crawler(cls, crawler: Crawler, *args, **kwargs):
        """
        Override existing from_crawler method to set spider_idle signal connection
        """
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.crawl_next_batch, signal=spider_idle)
        return spider

    @classmethod
    def update_settings(cls, settings: BaseSettings) -> None:
        """
        Apply project-wider common settings as well as custom settings at the spider priority level
        for just this spider.
        """
        super().update_settings(settings)
        settings.setmodule(module="search_gov_crawler.search_gov_spiders.settings.freshness_spider", priority="spider")
