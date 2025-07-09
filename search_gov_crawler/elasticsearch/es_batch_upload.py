import logging
import os
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from elasticsearch import Elasticsearch, helpers  # pylint: disable=wrong-import-order

from search_gov_crawler.elasticsearch.convert_html_i14y import convert_html
from search_gov_crawler.elasticsearch.convert_pdf_i14y import convert_pdf
from search_gov_crawler.elasticsearch.i14y_helper import update_dap_visits_to_document
from search_gov_crawler.search_gov_spiders.spiders import SearchGovDomainSpider

# limit excess INFO messages from elasticsearch that are not tied to a spider
logging.getLogger("elastic_transport").setLevel(logging.ERROR)

log = logging.getLogger("search_gov_crawler.elasticsearch")


class SearchGovElasticsearch:
    """Manages batching and bulk-upload of scraped documents to Elasticsearch."""

    def __init__(
        self,
        batch_size: int = 50,
        es_hosts: Optional[str] = None,
        es_index: Optional[str] = None,
        es_user: Optional[str] = None,
        es_password: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize batch and ES client parameters.

        Args:
            batch_size: number of docs to buffer before bulk upload
            es_hosts: comma-separated ES URLs (e.g. "https://host1:9200,https://host2:9200")
            es_index: Elasticsearch index name
            es_user: Basic auth username
            es_password: Basic auth password
            timeout: client request timeout in seconds
            max_retries: how many times to retry on failure
        """
        self._batch_size = batch_size
        self._current_batch: List[Dict[str, Any]] = []

        self._env_es_hosts = es_hosts or os.getenv("ES_HOSTS", "http://localhost:9200")
        self._env_es_index = es_index or os.getenv(
            "SEARCHELASTIC_INDEX", "development-i14y-documents-searchgov"
        )
        self._env_es_user = es_user or os.getenv("ES_USER", "")
        self._env_es_password = es_password or os.getenv("ES_PASSWORD", "")
        self._timeout = timeout
        self._max_retries = max_retries
        self._es_client: Optional[Elasticsearch] = None

        try:
            self._parsed_hosts = self._parse_es_urls(self._env_es_hosts)
        except ValueError:
            log.exception("Environment variable ES_HOSTS is malformed")
            raise

    @property
    def index_name(self) -> str:
        """ES index name."""
        return self._env_es_index

    @property
    def client(self) -> Elasticsearch:
        """Lazily initialize and return the ES client."""
        if self._es_client is None:
            self._es_client = Elasticsearch(
                hosts=self._parsed_hosts,
                basic_auth=(self._env_es_user, self._env_es_password)
                if self._env_es_user or self._env_es_password
                else None,
                verify_certs=False,
                request_timeout=self._timeout,
                max_retries=self._max_retries,
                retry_on_timeout=True,
            )
        return self._es_client  # type: ignore

    def add_to_batch(
        self,
        response_bytes: bytes,
        url: str,
        spider: SearchGovDomainSpider,
        response_language: str,
        content_type: str,
    ) -> None:
        """
        Convert a response into an i14y document and add to the batch.
        """
        try:
            if content_type == "text/html":
                doc = convert_html(response_bytes, url, response_language)
            elif content_type == "application/pdf":
                doc = convert_pdf(response_bytes, url, response_language)
            else:
                spider.logger.warning(
                    "Unsupported content type %r for URL %s; skipping", content_type, url
                )
                return

        except Exception:
            spider.logger.exception("Failed to convert %s (type %s): %s", url, content_type)
            return

        if not doc:
            spider.logger.warning("No document generated for URL %s", url)
            return

        try:
            doc = update_dap_visits_to_document(doc, spider)
        except Exception as e:
            spider.logger.exception("Failed to update DAP visits for url: %s, content_type: %s", url, content_type)
            # still continue to include the doc without DAP data

        self._current_batch.append(doc)
        if len(self._current_batch) >= self._batch_size:
            self.batch_upload(spider)

    def _create_actions(self, docs: List[Dict[str, Any]], spider: SearchGovDomainSpider) -> List[Dict[str, Any]]:
        """Build bulk actions, popping out any explicit _id fields."""
        actions: List[Dict[str, Any]] = []
        for doc in docs:
            action: Dict[str, Any] = {"_index": self._env_es_index}
            if "_id" in doc:
                action["_id"] = doc.pop("_id")
            else:
                spider.logger.error("Missing _id property in document: %s", doc)
                continue
            action["_source"] = doc
            actions.append(action)
        return actions

    def batch_upload(self, spider: SearchGovDomainSpider) -> None:
        """Send batch of documents to Elasticsearch via bulk API."""
        if not self._current_batch:
            return

        batch = self._current_batch
        self._current_batch = []

        actions = self._create_actions(batch, spider)
        failure_count = 0
        failures: List[Any] = []

        try:
            for ok, info in helpers.parallel_bulk(
                client=self.client,
                actions=actions,
                thread_count=4,
                queue_size=4,
                chunk_size=self._batch_size,
                max_chunk_bytes=10 * 1024 * 1024,
            ):
                if not ok:
                    failure_count += 1
                    failures.append(info)

            if not failure_count:
                    spider.logger.info("Loaded %s records to Elasticsearch!", len(batch))
            else:
                spider.logger.error(
                    "Failed to index %d documents; errors: %r", failure_count, failures
                )

        except Exception as e:
            spider.logger.exception("Bulk upload to ES failed: %s", e)

    def _parse_es_urls(self, url_string: str) -> List[Dict[str, Union[str, int]]]:
        """Parse comma-separated ES URLs into host dicts."""
        hosts: List[Dict[str, Union[str, int]]] = []
        for raw in url_string.split(","):
            parsed = urlparse(raw.strip())
            if not parsed.scheme or not parsed.hostname or not parsed.port:
                raise ValueError(f"Invalid Elasticsearch URL: {raw!r}")
            hosts.append(
                {"host": parsed.hostname, "port": parsed.port, "scheme": parsed.scheme}
            )
        return hosts
