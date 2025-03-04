import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urlparse

from elasticsearch import Elasticsearch, helpers
from scrapy.spiders import Spider

from search_gov_crawler.elasticsearch.convert_html_i14y import convert_html
from pythonjsonlogger.json import JsonFormatter
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT

# limit excess INFO messages from elasticsearch that are not tied to a spider
logging.getLogger("elastic_transport.transport").setLevel("ERROR")

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("search_gov_crawler.elasticsearch")


class SearchGovElasticsearch:
    """Defines the shape and methods of the spider's connection to Elasticsearch"""

    def __init__(self, batch_size: int = 50):
        self._current_batch = []
        self._batch_size = batch_size
        self._es_client = None
        self._env_es_hosts = os.environ.get("ES_HOSTS", "")
        self._env_es_index_name = os.environ.get("SPIDER_ES_INDEX_NAME", "")
        self._env_es_username = os.environ.get("ES_USER", "")
        self._env_es_password = os.environ.get("ES_PASSWORD", "")
        self._executor = ThreadPoolExecutor(max_workers=5)  # Reuse one executor

    def add_to_batch(self, html_content: str, url: str, spider: Spider):
        """
        Add a document to the batch for Elasticsearch upload.
        """
        doc = convert_html(html_content=html_content, url=url)
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
            except Exception as e:
                log.error(f"Couldn't create an elasticsearch client: {str(e)}")
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
                success, _ = helpers.bulk(self._get_client(), actions)
                spider.logger.info("Loaded %s records to Elasticsearch!", success)
            except Exception as e:
                spider.logger.error(f"Error in bulk upload: {str(e)}")

        await loop.run_in_executor(self._executor, _bulk_upload)
