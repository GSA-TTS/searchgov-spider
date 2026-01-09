import time
import logging
import os
import warnings
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from opensearchpy import OpenSearch, helpers

from search_gov_crawler.search_gov_spiders.spiders import SearchGovDomainSpider

from search_gov_crawler.search_engines.i14y_helper import generate_url_sha256


# Suppress warnings from urllib3 and OpenSearch client. Already doing this in es_batch_upload,
# but we want keep it here for when we remove Elasticsearch
warnings.filterwarnings("ignore", category=Warning, module="urllib3")
warnings.filterwarnings("ignore", category=Warning, module="opensearchpy")

# limit excess INFO messages from the OpenSearch transport
# opensearch-py exposes transport internals under opensearchpy.transport
logging.getLogger("opensearchpy.transport").setLevel(logging.ERROR)

log = logging.getLogger("search_gov_crawler.search_engines")


class SearchGovOpensearch:
    """Manages batching and bulk-upload of scraped documents to Opensearch."""

    ENABLED = os.environ.get("OPENSEARCH_ENABLED") == "True"

    def __init__(
        self,
        batch_size: int = 50,
        opensearch_host: Optional[str] = None,
        opensearch_index: Optional[str] = None,
        opensearch_user: Optional[str] = None,
        opensearch_password: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize batch and Opensearch client parameters.

        Args:
            batch_size: number of docs to buffer before bulk upload
            opensearch_host: Opensearch host URL with port (e.g. "https://host1:9200")
            opensearch_index: Opensearch index name
            opensearch_user: Basic auth username
            opensearch_password: Basic auth password
            timeout: client request timeout in seconds
            max_retries: how many times to retry on failure
        """
        self._batch_size = batch_size
        self._current_batch: List[Dict[str, Any]] = []
        self._env_opensearch_host = opensearch_host or os.getenv("OPENSEARCH_SEARCH_HOST", f"http://localhost:9200")
        self._env_opensearch_index = opensearch_index or os.getenv(
            "OPENSEARCH_SEARCH_INDEX",
            "development-i14y-documents-searchgov",
        )
        self._env_opensearch_user = opensearch_user or os.getenv("OPENSEARCH_SEARCH_USER", "")
        self._env_opensearch_password = opensearch_password or os.getenv("OPENSEARCH_SEARCH_PASSWORD", "")
        self._timeout = timeout
        self._max_retries = max_retries
        self._opensearch_client: Optional[OpenSearch] = None

    @property
    def index_name(self) -> str:
        """Opensearch index name."""
        return self._env_opensearch_index

    @property
    def client(self) -> OpenSearch:
        """Lazily initialize and return the Opensearch client."""
        if self._opensearch_client is None:
            self._opensearch_client = OpenSearch(
                hosts=self._env_opensearch_host,
                http_auth=(self._env_opensearch_user, self._env_opensearch_password)
                if self._env_opensearch_user or self._env_opensearch_password
                else None,
                use_ssl=self._env_opensearch_host.startswith("https://"),
                verify_certs=False,
                ssl_show_warn=False,
                timeout=self._timeout,
                max_retries=self._max_retries,
                retry_on_timeout=True,
            )
        return self._opensearch_client  # type: ignore

    def add_to_batch(
        self,
        doc: dict[str, Any] | None,
        spider: SearchGovDomainSpider,
    ) -> None:
        """Add an already converted i14y document to the Opensearch batch.

        NOTE: The creation of the i14y document "doc" is done in es_batch_upload.py > add_to_batch() method.
              We are not calling convert_html(), convert_pdf(), and etc. in this method, and they will need
              to be added once we completely migrate to Opensearch and disable Elasticsearch

        Args:
            doc: dict The already converted i14y document
            spider: SearchGovDomainSpider The scrapy spider
        """
        if not self.ENABLED or not doc:
            return

        self._current_batch.append(doc)
        if len(self._current_batch) >= self._batch_size:
            self.batch_upload(spider)

    def _create_actions(self, docs: List[Dict[str, Any]], spider: SearchGovDomainSpider) -> List[Dict[str, Any]]:
        """Build bulk actions, popping out any explicit _id fields."""
        actions: List[Dict[str, Any]] = []
        for doc in docs:
            action: Dict[str, Any] = {"_index": self._env_opensearch_index}
            if "path" in doc:
                action["_id"] = generate_url_sha256(doc["path"])
            else:
                spider.logger.error("Missing required 'path' property in document: %s", doc)
                continue
            action["_source"] = doc
            actions.append(action)
        return actions

    def batch_upload(self, spider: SearchGovDomainSpider) -> None:
        """Send batch of documents to Opensearch via bulk API."""

        # TODO: Remove this delay once Elasticsearch is removed.
        # Opensearch has a 5 second delay before it sends its batch
        # to not compete with elasticsearch batches for resources when sent simultaneously
        time.sleep(5)

        if not self._current_batch or not self.ENABLED:
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
                spider.logger.info("Loaded %s records to Opensearch!", len(batch))
            else:
                spider.logger.error("Failed to index %d documents; errors: %r", failure_count, failures)

        except Exception:
            spider.logger.exception("Bulk upload to Opensearch failed")

    def _parse_opensearch_urls(self, url_string: str) -> List[Dict[str, Union[str, int]]]:
        """Parse comma-separated Opensearch URLs into host dicts."""
        hosts: List[Dict[str, Union[str, int]]] = []
        for raw in url_string.split(","):
            parsed = urlparse(raw.strip())
            if not parsed.scheme or not parsed.hostname or not parsed.port:
                raise ValueError(f"Invalid Opensearch URL: {raw!r}")
            hosts.append({"host": parsed.hostname, "port": parsed.port, "scheme": parsed.scheme})
        return hosts
