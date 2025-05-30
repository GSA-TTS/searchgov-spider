import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urlparse

from elasticsearch import Elasticsearch, helpers  # pylint: disable=wrong-import-order
from scrapy.spiders import Spider

from search_gov_crawler.elasticsearch.convert_html_i14y import convert_html
from search_gov_crawler.elasticsearch.convert_pdf_i14y import convert_pdf

# limit excess INFO messages from elasticsearch that are not tied to a spider
logging.getLogger("elastic_transport").setLevel("ERROR")

log = logging.getLogger("search_gov_crawler.elasticsearch")

"""
Temporary variable to disable the PDF functionality until we're ready to launch it
"""
DISABLE_PDF = False


class SearchGovElasticsearch:
    """Defines the shape and methods of the spider's connection to Elasticsearch"""

    def __init__(self, batch_size: int = 50):
        self._current_batch = []
        self._batch_size = batch_size
        self._es_client = None
        self._env_es_hosts = os.environ.get("ES_HOSTS", "http://localhost:9200")
        self._env_es_index_name = os.environ.get("SEARCHELASTIC_INDEX", "development-i14y-documents-searchgov")
        self._env_es_username = os.environ.get("ES_USER", "")
        self._env_es_password = os.environ.get("ES_PASSWORD", "")
        self._executor = ThreadPoolExecutor(max_workers=5)  # Reuse one executor

    def add_to_batch(self, response_bytes: bytes, url: str, spider: Spider, response_language: str, content_type: str):
        """
        Add a document to the batch for Elasticsearch upload.
        """
        doc = None
        if content_type == "text/html":
            doc = convert_html(response_bytes=response_bytes, url=url, response_language=response_language)
        elif content_type == "application/pdf" and not DISABLE_PDF:
            doc = convert_pdf(response_bytes=response_bytes, url=url, response_language=response_language)

        if doc:
            self._current_batch.append(doc)

            if len(self._current_batch) >= self._batch_size:
                self.batch_upload(spider)
        else:
            spider.logger.warning(f"Did not create i14y document for URL: {url}")

    def batch_upload(self, spider: Spider):
        """
        Initiates batch upload using asyncio.
        """
        if not self._current_batch:
            return

        current_batch_copy = self._current_batch.copy()
        self._current_batch = []

        loop = asyncio.get_running_loop() if asyncio.get_event_loop().is_running() else asyncio.new_event_loop()
        asyncio.ensure_future(self._batch_elasticsearch_upload(current_batch_copy, loop, spider))

    def _parse_es_urls(self, url_string: str) -> list[dict[str, Any]]:
        """
        Parse Elasticsearch hosts from a comma-separated string.
        """
        hosts = []
        for url in url_string.split(","):
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.hostname or not parsed.port:
                raise ValueError(f"Invalid Elasticsearch URL: {url}")

            hosts.append({"host": parsed.hostname, "port": parsed.port, "scheme": parsed.scheme})
        return hosts

    @property
    def client(self) -> Elasticsearch:
        """
        Returns the Elasticsearch client.  Helper method for scripts and other external useage.
        """
        if not self._es_client:
            self._es_client = self._get_client()
        return self._es_client

    @property
    def index_name(self) -> str:
        """Returns the index name.  Helper method for scripts and other external usage."""
        return self._env_es_index_name

    def _get_client(self):
        """
        Lazily initializes the Elasticsearch client.
        """
        if not self._es_client:
            try:
                self._es_client = Elasticsearch(
                    hosts=self._parse_es_urls(self._env_es_hosts),
                    verify_certs=False,
                    ssl_show_warn=False,
                    basic_auth=(self._env_es_username, self._env_es_password),
                )
            except Exception:  # pylint: disable=broad-except
                log.exception("Couldn't create an elasticsearch client")
        return self._es_client

    def _create_actions(self, docs: list[dict[Any, Any]]) -> list[dict[str, Any]]:
        """
        Create actions for bulk upload from documents.
        """
        return [{"_index": self._env_es_index_name, "_id": doc.pop("_id", None), "_source": doc} for doc in docs]

    async def _batch_elasticsearch_upload(self, docs: list[dict[Any, Any]], loop, spider: Spider):
        """
        Perform bulk upload asynchronously using ThreadPoolExecutor.
        """

        def _bulk_upload():
            try:
                actions = self._create_actions(docs)
                success, errors = helpers.bulk(self._get_client(), actions, raise_on_error=False)
                if success:
                    spider.logger.info("Loaded %s records to Elasticsearch!", success)
                if errors:
                    spider.logger.error("Error in bulk upload: %s document(s) failed to index: %s", len(errors), errors)
            except Exception:  # pylint: disable=broad-except
                spider.logger.exception("Error in bulk upload")

        await loop.run_in_executor(self._executor, _bulk_upload)
