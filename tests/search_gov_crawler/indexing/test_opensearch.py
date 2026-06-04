import pytest
from opensearchpy.exceptions import RequestError

from search_gov_crawler.indexing.helpers import generate_url_sha256
from search_gov_crawler.indexing.opensearch import SearchGovOpensearch


@pytest.fixture
def mock_spider(mocker):
    spider = mocker.MagicMock()
    spider.logger = mocker.MagicMock()
    return spider


@pytest.fixture
def opensearch_instance():
    # Ensure ENABLED is True for testing
    return SearchGovOpensearch(
        batch_size=2,
        opensearch_host="http://localhost:9300",
        opensearch_index="test-index",
    )


def test_index_name_property(opensearch_instance):
    assert opensearch_instance.index_name == "test-index"


def test_client_lazy_init(mocker, opensearch_instance):
    mock_client = mocker.MagicMock()
    mock_cls = mocker.patch("search_gov_crawler.indexing.opensearch.OpenSearch", return_value=mock_client)
    client = opensearch_instance.client
    assert client == mock_client
    mock_cls.assert_called_once()
    # Ensure second call reuses cached client
    assert opensearch_instance.client is mock_client


def test_add_to_batch_triggers_upload(mocker, opensearch_instance, mock_spider):
    mock_upload = mocker.patch.object(opensearch_instance, "batch_upload")
    doc1 = {"_id": "1", "field": "value"}
    doc2 = {"_id": "2", "field": "value"}
    opensearch_instance.add_to_batch(doc1, mock_spider)
    opensearch_instance.add_to_batch(doc2, mock_spider)  # should trigger batch_upload
    mock_upload.assert_called_once()


def test_add_to_batch_no_doc(mocker, opensearch_instance, mock_spider):
    mock_upload = mocker.patch.object(opensearch_instance, "batch_upload")
    opensearch_instance.add_to_batch(None, mock_spider)
    mock_upload.assert_not_called()


def test_create_actions_with_and_without_id(opensearch_instance, mock_spider):
    path = "http://www.example.com/1"
    doc_id = generate_url_sha256(path)
    docs = [{"id": doc_id, "path": path, "field": "value"}, {"id": None, "field": "missing id"}]
    actions = opensearch_instance._create_actions(docs, mock_spider)
    assert actions == [
        {
            "_index": "test-index",
            "_id": doc_id,
            "_source": {"path": "http://www.example.com/1", "field": "value", "id": doc_id},
        },
    ]
    mock_spider.logger.error.assert_called_once()


def test_batch_upload_success(mocker, opensearch_instance, mock_spider):
    docs = [{"id": "1", "field": "v1"}, {"id": "2", "field": "v2"}]
    opensearch_instance._current_batch = docs.copy()

    mock_bulk = mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk")
    mock_bulk.return_value = iter([(True, {"index": {}}), (True, {"index": {}})])

    mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk", return_value=mock_bulk)
    opensearch_instance.batch_upload(mock_spider)

    mock_spider.logger.info.assert_called_once_with("Loaded %s records to Opensearch!", 2)


def test_batch_upload_failure(mocker, opensearch_instance, mock_spider):
    path = "http://www.example.com/1"
    docs = [{"path": path, "field": "v1", "id": "asdf"}]
    opensearch_instance._current_batch = docs.copy()

    mock_bulk = [(False, {"error": "failed"})]
    mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk", return_value=mock_bulk)
    opensearch_instance.batch_upload(mock_spider)

    mock_spider.logger.error.assert_called_once()


def test_batch_upload_exception(mocker, opensearch_instance, mock_spider):
    docs = [{"id": "1", "field": "v1"}]
    opensearch_instance._current_batch = docs.copy()

    mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk", side_effect=Exception("boom"))
    opensearch_instance.batch_upload(mock_spider)

    mock_spider.logger.exception.assert_called_once_with("Bulk upload to Opensearch failed")


def test_batch_upload_no_docs(mocker, opensearch_instance, mock_spider):
    opensearch_instance._current_batch = []
    mock_bulk = mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk")
    opensearch_instance.batch_upload(mock_spider)
    mock_bulk.assert_not_called()


@pytest.mark.parametrize("return_val", [True, False])
def test_index_exists(mocker, opensearch_instance, return_val):
    mock_client = mocker.MagicMock()
    mocker.patch("search_gov_crawler.indexing.opensearch.OpenSearch", return_value=mock_client)
    mock_client.indices.exists.return_value = return_val
    assert opensearch_instance.index_exists() is return_val


def test_create_index(mocker, opensearch_instance):
    mock_client = mocker.MagicMock()
    mocker.patch("search_gov_crawler.indexing.opensearch.OpenSearch", return_value=mock_client)
    opensearch_instance.create_index(template={"this_is": "a_template"})
    mock_client.indices.create.assert_called_once()


def test_update_index_template(mocker, opensearch_instance):
    mock_client = mocker.MagicMock()
    mocker.patch("search_gov_crawler.indexing.opensearch.OpenSearch", return_value=mock_client)
    mock_client.inidices.exists.return_value = False
    opensearch_instance.update_index_template(template={"mappings": {}, "settings": {}})
    mock_client.indices.put_mapping.assert_called_once()
    mock_client.indices.put_settings.assert_called_once()


def test_update_index_request_error(mocker, opensearch_instance):
    mock_client = mocker.MagicMock()
    mocker.patch("search_gov_crawler.indexing.opensearch.OpenSearch", return_value=mock_client)
    mock_client.indices.put_mapping.side_effect = [RequestError(400, "You didn't say the magic word!")]
    with pytest.raises(RequestError, match="You didn't say the magic word!"):
        opensearch_instance.update_index_template(template={"mappings": {}, "settings": {}})


def test_update_index_template_index_does_not_exist(caplog, mocker, opensearch_instance):
    mock_client = mocker.MagicMock()
    mocker.patch("search_gov_crawler.indexing.opensearch.OpenSearch", return_value=mock_client)
    mock_client.indices.exists.return_value = False
    with caplog.at_level("INFO"):
        opensearch_instance.update_index_template(template={"mappings": {}, "settings": {}})

    assert "Index test-index does not exist, create it first!" in caplog.messages
