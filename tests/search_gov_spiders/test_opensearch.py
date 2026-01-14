import pytest
from unittest.mock import MagicMock, patch
from search_gov_crawler.search_engines.opensearch_batch_upload import SearchGovOpensearch
from search_gov_crawler.search_engines.i14y_helper import generate_url_sha256

@pytest.fixture
def mock_spider():
    spider = MagicMock()
    spider.logger = MagicMock()
    return spider


@pytest.fixture
def opensearch_instance(monkeypatch):
    # Ensure ENABLED is True for testing
    monkeypatch.setattr(SearchGovOpensearch, "ENABLED", True)
    return SearchGovOpensearch(
        batch_size=2,
        opensearch_host="http://localhost:9300",
        opensearch_index="test-index",
    )


def test_index_name_property(opensearch_instance):
    assert opensearch_instance.index_name == "test-index"


def test_client_lazy_init(opensearch_instance):
    mock_client = MagicMock()
    with patch("search_gov_crawler.search_engines.opensearch_batch_upload.OpenSearch", return_value=mock_client) as mock_cls:
        client = opensearch_instance.client
        assert client == mock_client
        mock_cls.assert_called_once()
        # Ensure second call reuses cached client
        assert opensearch_instance.client is mock_client


def test_add_to_batch_triggers_upload(opensearch_instance, mock_spider):
    with patch.object(opensearch_instance, "batch_upload") as mock_upload:
        doc1 = {"_id": "1", "field": "value"}
        doc2 = {"_id": "2", "field": "value"}
        opensearch_instance.add_to_batch(doc1, mock_spider)
        opensearch_instance.add_to_batch(doc2, mock_spider)  # should trigger batch_upload
        assert mock_upload.called


def test_add_to_batch_disabled(monkeypatch, opensearch_instance, mock_spider):
    monkeypatch.setattr(SearchGovOpensearch, "ENABLED", False)
    with patch.object(opensearch_instance, "batch_upload") as mock_upload:
        opensearch_instance.add_to_batch({"_id": "1", "field": "value"}, mock_spider)
        assert not mock_upload.called


def test__create_actions_with_and_without_path(opensearch_instance, mock_spider):
    path = "http://www.example.com/1"
    id = generate_url_sha256(path)
    docs = [
        {"path": path, "field": "value"},
        {"field": "missing id"}
    ]
    actions = opensearch_instance._create_actions(docs, mock_spider)
    assert actions == [{"_index": "test-index", "_id": id, "_source": {'path': 'http://www.example.com/1', "field": "value"}}]
    mock_spider.logger.error.assert_called_once()


def test_batch_upload_success(mocker, opensearch_instance, mock_spider):
    docs = [{"_id": "1", "field": "v1"}, {"_id": "2", "field": "v2"}]
    opensearch_instance._current_batch = docs.copy()

    mock_bulk = mocker.patch("search_gov_crawler.search_engines.es_batch_upload.helpers.parallel_bulk")
    mock_bulk.return_value = iter([(True, {"index": {}}), (True, {"index": {}})])

    with patch("search_gov_crawler.search_engines.opensearch_batch_upload.helpers.parallel_bulk", return_value=mock_bulk()):
        opensearch_instance.batch_upload(mock_spider)

    mock_spider.logger.info.assert_called_once_with("Loaded %s records to Opensearch!", 2)


def test_batch_upload_failure(opensearch_instance, mock_spider):
    path = "http://www.example.com/1"
    docs = [{"path": path, "field": "v1"}]
    opensearch_instance._current_batch = docs.copy()

    mock_bulk = [(False, {"error": "failed"})]
    with patch("search_gov_crawler.search_engines.opensearch_batch_upload.helpers.parallel_bulk", return_value=mock_bulk):
        opensearch_instance.batch_upload(mock_spider)

    mock_spider.logger.error.assert_called_once()


def test_batch_upload_exception(opensearch_instance, mock_spider):
    docs = [{"_id": "1", "field": "v1"}]
    opensearch_instance._current_batch = docs.copy()

    with patch("search_gov_crawler.search_engines.opensearch_batch_upload.helpers.parallel_bulk", side_effect=Exception("boom")):
        opensearch_instance.batch_upload(mock_spider)

    mock_spider.logger.exception.assert_called_once_with("Bulk upload to Opensearch failed")


def test_batch_upload_no_docs(opensearch_instance, mock_spider):
    opensearch_instance._current_batch = []
    with patch("search_gov_crawler.search_engines.opensearch_batch_upload.helpers.parallel_bulk") as mock_bulk:
        opensearch_instance.batch_upload(mock_spider)
        mock_bulk.assert_not_called()
