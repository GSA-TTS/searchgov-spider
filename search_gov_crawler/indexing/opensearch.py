import logging
from collections.abc import Generator
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
    def batch_size(self) -> int:
        """Current batch size for parallel bulk"""
        return self._batch_size

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

    def _resolved_index_name(self, index_name: str | None = None) -> str:
        """Resuable private method to resolve index name arguments as the passed value or the default"""
        return index_name or self.index_name

    def add_to_batch(self, doc: dict[str, Any] | None, operation: str = "index", index_name: str | None = None) -> None:
        """Add a document to the Opensearch batch.

        Args:
            doc: dict The document to be indexed, which must include an "id" field for the document ID in Opensearch
            operation: string The type of action to take on the doc in the index.
            index_name: string The index to perform the action on
        """
        if not doc:
            return

        self._current_batch.append((operation, self._resolved_index_name(index_name), doc))
        if len(self._current_batch) >= self._batch_size:
            self.batch_upload()

    def _create_actions(self, batch: list[tuple[str, str, dict]]) -> list[dict[str, Any]]:
        """Build bulk actions basd on operation type"""
        actions: list[dict[str, Any]] = []

        for operation, index_name, doc in batch:
            id_field = "_id" if operation == "delete" else "id"
            if id_value := doc.get(id_field):
                action = {"_op_type": operation, "_index": index_name, "_id": id_value, "_source": doc}
            else:
                self.logger.error("Missing required '%s' property in document: %s", id_field, doc)
                continue
            actions.append(action)
        return actions

    def bulk_batch_upload(self, batch: list[tuple[str, str, dict]]) -> tuple[list, list]:
        """
        Allow use of batch upload bypassing normal addition of documents one by one.  Process documents
        in batch and return docs in either success or error buckets for additional processing.
        """

        successful_actions = []
        failed_actions = []
        actions = self._create_actions(batch=batch)
        for success, info in self._get_parallel_bulk_generator(actions=actions):
            if success:
                successful_actions.append(info)
            else:
                failed_actions.append(info)

        return successful_actions, failed_actions

    def batch_upload(self) -> None:
        """Send current batch of documents to Opensearch via bulk API."""

        if not self._current_batch:
            return

        batch = self._current_batch
        self._current_batch = []

        actions = self._create_actions(batch)
        failure_count = 0
        failures: list[Any] = []

        try:
            for ok, info in self._get_parallel_bulk_generator(actions=actions):
                if not ok:
                    failure_count += 1
                    failures.append(info)

            if not failure_count:
                self.logger.info("Performed %s actions on Opensearch!", len(batch))
            else:
                self.logger.error("Failed to perform actions on %d documents; errors: %r", failure_count, failures)

        except Exception:
            self.logger.exception("Bulk upload to Opensearch failed")

    def _get_parallel_bulk_generator(self, actions) -> Generator[Any, None, None]:
        """Allows reuse between multiple methos calling the parallel_bulk helper"""
        return helpers.parallel_bulk(
            client=self.client,
            actions=actions,
            thread_count=4,
            queue_size=4,
            chunk_size=self._batch_size,
            max_chunk_bytes=10 * 1024 * 1024,
            raise_on_error=False,
        )

    def index_exists(self, index_name: str | None = None) -> bool:
        """Wrapper around opensearch-py client check"""
        return self.client.indices.exists(index=self._resolved_index_name(index_name))

    def create_index(self, template: dict, index_name: str | None = None) -> None:
        """Creates index with a given template"""
        resolved_index_name = self._resolved_index_name(index_name)
        self.client.indices.create(index=resolved_index_name, body=template)
        log.info("Created index %s with template!", resolved_index_name)

    def update_index_template(self, template: dict, index_name: str | None = None) -> None:
        """Updates index with a given template"""

        resolved_index_name = self._resolved_index_name(index_name)
        if self.index_exists(resolved_index_name):
            try:
                self.client.indices.put_mapping(index=resolved_index_name, body=template["mappings"])
                log.info("Updated mappings for index %s", resolved_index_name)
                self.client.indices.put_settings(index=resolved_index_name, body=template["settings"])
                log.info("Updated settings for index %s", resolved_index_name)
            except (KeyError, RequestError):
                log.exception("Error updating index %s", resolved_index_name)
                raise
        else:
            log.error("Index %s does not exist, create it first!", resolved_index_name)
