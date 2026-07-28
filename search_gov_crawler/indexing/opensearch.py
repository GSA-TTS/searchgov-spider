import logging
from logging import Logger, LoggerAdapter
from typing import Any

from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import RequestError

from search_gov_crawler.config.settings import SearchgovSettings

# limit excess INFO messages from the OpenSearch transport
# opensearch-py exposes transport internals under opensearchpy.transport
logging.getLogger("opensearchpy.transport").setLevel(logging.ERROR)
log = logging.getLogger(__name__)


class SearchGovOpensearch:
    """Manages batching and bulk-upload of scraped documents to Opensearch."""

    def __init__(
        self,
        searchgov_settings: SearchgovSettings,
        batch_size: int = 50,
        opensearch_host: str | None = None,
        opensearch_index: str | None = None,
        opensearch_user: str | None = None,
        opensearch_password: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
        logger: Logger | LoggerAdapter = log,
    ) -> None:
        """Initialize batch and Opensearch client parameters.

        Args:
            settings: An instance of SearchgovSpiderSettings
            action: the type of bulk action to take in opensearch
            batch_size: number of docs to buffer before bulk upload
            timeout: client request timeout in seconds
            max_retries: how many times to retry on failure
        """
        self.searchgov_settings = searchgov_settings
        self._batch_size = batch_size
        self._current_batch: list[tuple[str, str, dict]] = []
        self._opensearch_host = opensearch_host or self.searchgov_settings.opensearch_search_host
        self._opensearch_index = opensearch_index or self.searchgov_settings.opensearch_search_index
        self._opensearch_user = opensearch_user or self.searchgov_settings.opensearch_search_user
        self._opensearch_password = opensearch_password or self.searchgov_settings.opensearch_search_password
        self._timeout = timeout
        self._max_retries = max_retries
        self._opensearch_client: OpenSearch | None = None
        self.logger = logger

    @property
    def index_name(self) -> str:
        """Opensearch index name."""
        return self._opensearch_index

    @property
    def client(self) -> OpenSearch:
        """Lazily initialize and return the Opensearch client."""
        if self._opensearch_client is None:
            self._opensearch_client = OpenSearch(
                hosts=self._opensearch_host,
                http_auth=(self._opensearch_user, self._opensearch_password)
                if self._opensearch_user or self._opensearch_password
                else None,
                use_ssl=self._opensearch_host.startswith("https://"),
                verify_certs=False,
                ssl_show_warn=False,
                timeout=self._timeout,
                max_retries=self._max_retries,
                retry_on_timeout=True,
            )
        return self._opensearch_client

    def add_to_batch(self, doc: dict[str, Any] | None, operation: str = "index", index_name: str | None = None) -> None:
        """Add a document to the Opensearch batch.

        Args:
            doc: dict The document to be indexed, which must include an "id" field for the document ID in Opensearch
        """
        if not doc:
            return

        self._current_batch.append((operation, index_name or self.index_name, doc))
        if len(self._current_batch) >= self._batch_size:
            self.batch_upload()

    def _create_actions(self, batch: list[tuple[str, str, dict]]) -> list[dict[str, Any]]:
        """Build bulk actions, popping out any explicit _id fields."""
        actions: list[dict[str, Any]] = []
        for operation, index_name, doc in batch:
            if doc["id"]:
                action = {"_op_type": operation, "_index": index_name, "_id": doc["id"], "_source": doc}
            else:
                self.logger.error("Missing required 'id' property in document: %s", doc)
                continue
            actions.append(action)
        return actions

    def batch_upload(self) -> None:
        """Send batch of documents to Opensearch via bulk API."""

        if not self._current_batch:
            return

        batch = self._current_batch
        self._current_batch = []

        actions = self._create_actions(batch)
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
                self.logger.info("Loaded %s records to Opensearch!", len(batch))
            else:
                self.logger.error("Failed to index %d documents; errors: %r", failure_count, failures)

        except Exception:
            self.logger.exception("Bulk upload to Opensearch failed")

    def index_exists(self) -> bool:
        """Wrapper around opensearch-py client check"""
        return self.client.indices.exists(index=self.index_name)

    def create_index(self, template: dict) -> None:
        """Creates index with a given template"""
        self.client.indices.create(index=self.index_name, body=template)
        log.info("Created index %s with template!", self.index_name)

    def update_index_template(self, template: dict) -> None:
        """Updates index with a given template"""

        if self.index_exists():
            try:
                self.client.indices.put_mapping(index=self.index_name, body=template["mappings"])
                log.info("Updated mappings for index %s", self.index_name)
                self.client.indices.put_settings(index=self.index_name, body=template["settings"])
                log.info("Updated settings for index %s", self.index_name)
            except (KeyError, RequestError):
                log.exception("Error updating index %s", self.index_name)
                raise
        else:
            log.error("Index %s does not exist, create it first!", self.index_name)
