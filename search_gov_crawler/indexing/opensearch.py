import logging
import os
from typing import Any

from opensearchpy import OpenSearch, helpers
from scrapy import Spider

# limit excess INFO messages from the OpenSearch transport
# opensearch-py exposes transport internals under opensearchpy.transport
logging.getLogger("opensearchpy.transport").setLevel(logging.ERROR)
log = logging.getLogger(__name__)


class SearchGovOpensearch:
    """Manages batching and bulk-upload of scraped documents to Opensearch."""

    def __init__(
        self,
        batch_size: int = 50,
        opensearch_host: str | None = None,
        opensearch_index: str | None = None,
        opensearch_user: str | None = None,
        opensearch_password: str | None = None,
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
        self._current_batch: list[dict[str, Any]] = []
        self._env_opensearch_host = opensearch_host or os.getenv("OPENSEARCH_SEARCH_HOST", "http://localhost:9200")
        self._env_opensearch_index = opensearch_index or os.getenv(
            "OPENSEARCH_SEARCH_INDEX",
            "development-i14y-documents-searchgov",
        )
        self._env_opensearch_user = opensearch_user or os.getenv("OPENSEARCH_SEARCH_USER", "")
        self._env_opensearch_password = opensearch_password or os.getenv("OPENSEARCH_SEARCH_PASSWORD", "")
        self._timeout = timeout
        self._max_retries = max_retries
        self._opensearch_client: OpenSearch | None = None

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
        return self._opensearch_client

    def add_to_batch(self, doc: dict[str, Any] | None, spider: Spider) -> None:
        """Add a document to the Opensearch batch.

        Args:
            doc: dict The document to be indexed, which must include an "id" field for the document ID in Opensearch
            spider:  The scrapy spider being used, for logging purposes
        """
        if not doc:
            return

        self._current_batch.append(doc)
        if len(self._current_batch) >= self._batch_size:
            self.batch_upload(spider)

    def _create_actions(self, docs: list[dict[str, Any]], spider: Spider) -> list[dict[str, Any]]:
        """Build bulk actions, popping out any explicit _id fields."""
        actions: list[dict[str, Any]] = []
        for doc in docs:
            if doc["id"]:
                action = {"_index": self._env_opensearch_index, "_id": doc["id"], "_source": doc}
            else:
                spider.logger.error("Missing required 'id' property in document: %s", doc)
                continue
            actions.append(action)
        return actions

    def batch_upload(self, spider: Spider) -> None:
        """Send batch of documents to Opensearch via bulk API."""

        if not self._current_batch:
            return

        batch = self._current_batch
        self._current_batch = []

        actions = self._create_actions(docs=batch, spider=spider)
        failure_count = 0
        failures: list[Any] = []

        try:
            for ok, info in helpers.parallel_bulk(
                client=self.client,
                actions=actions,
                thread_count=4,
                queue_size=4,
                chunk_size=self._batch_size,
                max_chunk_bytes=10 * 1024 * 1024,
                raise_on_error=False,
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
