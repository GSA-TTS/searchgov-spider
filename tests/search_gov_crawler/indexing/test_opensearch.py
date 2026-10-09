import re

import pytest
from opensearchpy.exceptions import NotFoundError, RequestError

from search_gov_crawler.config.settings import SearchgovSettings
from search_gov_crawler.indexing.helpers import generate_url_sha256
from search_gov_crawler.indexing.opensearch import SearchGovOpensearch


@pytest.fixture
def mock_searchgov_settings():
    return SearchgovSettings(opensearch_search_host="http://localhost:9300", opensearch_search_index="test-index")


@pytest.fixture
def opensearch_instance(mocker, mock_searchgov_settings):
    opensearch = SearchGovOpensearch(
        searchgov_settings=mock_searchgov_settings, batch_size=2, logger=mocker.MagicMock()
    )
    opensearch._opensearch_client = mocker.MagicMock()
    return opensearch


def test_index_name_property(opensearch_instance):
    assert opensearch_instance.index_name == "test-index"


def test_batch_size_property(opensearch_instance):
    assert opensearch_instance.batch_size == 2


@pytest.mark.parametrize(
    ("test_kwargs", "expected_output"),
    [({}, "test-index"), ({"index_name": "new-unit-test-index"}, "new-unit-test-index")],
)
def test_resolved_index_name(opensearch_instance, test_kwargs, expected_output):
    assert opensearch_instance._resolved_index_name(**test_kwargs) == expected_output


def test_client_lazy_init(mocker, opensearch_instance):
    opensearch_instance._opensearch_client = None
    mock_client = mocker.MagicMock()
    mock_cls = mocker.patch("search_gov_crawler.indexing.opensearch.OpenSearch", return_value=mock_client)
    client = opensearch_instance.client
    assert client == mock_client
    mock_cls.assert_called_once()
    # Ensure second call reuses cached client
    assert opensearch_instance.client is mock_client


def test_add_to_batch_triggers_upload(mocker, opensearch_instance):
    mock_upload = mocker.patch.object(opensearch_instance, "batch_upload")
    doc1 = {"_id": "1", "field": "value"}
    doc2 = {"_id": "2", "field": "value"}
    opensearch_instance.add_to_batch(doc1)
    opensearch_instance.add_to_batch(doc2)  # should trigger batch_upload
    mock_upload.assert_called_once()


def test_add_to_batch_no_doc(mocker, opensearch_instance):
    mock_upload = mocker.patch.object(opensearch_instance, "batch_upload")
    opensearch_instance.add_to_batch(None)
    mock_upload.assert_not_called()


def test_create_actions_index_with_and_without_id(opensearch_instance):
    path = "http://www.example.com/1"
    doc_id = generate_url_sha256(path)
    batch = [
        # good input
        ("index", "test-index", {"id": doc_id, "path": path, "field": "value"}),
        ("delete", "test-index", {"_id": doc_id}),
        # bad input
        ("index", "test-index", {"id": None, "field": "missing id"}),
        ("delete", "test-index", {"id": doc_id, "field": "wrong id field"}),
        ("index", "test-index", {"field": "there is no id"}),
        ("delete", "test-index", {"field": "there is no _id"}),
    ]
    actions = opensearch_instance._create_actions(batch=batch)
    assert actions == [
        {
            "_op_type": "index",
            "_index": "test-index",
            "_id": doc_id,
            "_source": {"path": "http://www.example.com/1", "field": "value", "id": doc_id},
        },
        {
            "_op_type": "delete",
            "_index": "test-index",
            "_id": doc_id,
            "_source": {"_id": doc_id},
        },
    ]
    assert opensearch_instance.logger.error.call_count == 4


def test_batch_upload_success(mocker, opensearch_instance):
    batch = [("index", "test-index", {"id": "1", "field": "v1"}), ("index", "test-index", {"id": "2", "field": "v2"})]
    opensearch_instance._current_batch = batch.copy()

    mock_bulk = mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk")
    mock_bulk.return_value = iter([(True, {"index": {}}), (True, {"index": {}})])

    mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk", return_value=mock_bulk)
    opensearch_instance.batch_upload()

    opensearch_instance.logger.info.assert_called_once_with("Performed %s actions on Opensearch!", 2)


def test_batch_upload_failure(mocker, opensearch_instance):
    batch = [("index", "test-index", {"path": "http://www.example.com/1", "field": "v1", "id": "asdf"})]
    opensearch_instance._current_batch = batch.copy()

    mock_bulk = [(False, {"error": "failed"})]
    mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk", return_value=mock_bulk)
    opensearch_instance.batch_upload()

    opensearch_instance.logger.error.assert_called_once()


def test_batch_upload_exception(mocker, opensearch_instance):
    batch = [("index", "test-index", {"id": "1", "field": "v1"})]
    opensearch_instance._current_batch = batch.copy()

    mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk", side_effect=Exception("boom"))
    opensearch_instance.batch_upload()

    opensearch_instance.logger.exception.assert_called_once_with("Bulk upload to Opensearch failed")


def test_batch_upload_no_docs(mocker, opensearch_instance):
    opensearch_instance._current_batch = []
    mock_bulk = mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk")
    opensearch_instance.batch_upload()
    mock_bulk.assert_not_called()


def test_bulk_batch_upload(mocker, opensearch_instance):
    mock_bulk = mocker.patch("search_gov_crawler.indexing.opensearch.helpers.parallel_bulk")
    mock_bulk.return_value = iter([(True, {"index": {}}), (True, {"delete": {}}), (False, {"index": {}})])

    batch = [
        ("index", "test-index", {"path": "http://www.example.com/1", "field": "v1", "id": "1234"}),
        ("delete", "test-index", {"_id": "5678"}),
        ("index", "non-existent-index", {"id": "9012", "path": "https://www.example.com/2", "field": "v2"}),
    ]
    successful_actions, failed_actions = opensearch_instance.bulk_batch_upload(batch)
    assert len(successful_actions) == 2
    assert len(failed_actions) == 1


@pytest.mark.parametrize("return_val", [True, False])
def test_index_exists(opensearch_instance, return_val):
    opensearch_instance.client.indices.exists.return_value = return_val
    assert opensearch_instance.index_exists() is return_val


def test_create_index(opensearch_instance):
    opensearch_instance.create_index(template={"this_is": "a_template"})
    opensearch_instance.client.indices.create.assert_called_once()


def test_update_index_template(opensearch_instance):
    opensearch_instance.client.inidices.exists.return_value = False
    opensearch_instance.update_index_template(template={"mappings": {}, "settings": {}})
    opensearch_instance.client.indices.put_mapping.assert_called_once()
    opensearch_instance.client.indices.put_settings.assert_called_once()


def test_update_index_request_error(opensearch_instance):
    opensearch_instance.client.indices.put_mapping.side_effect = [RequestError(400, "You didn't say the magic word!")]
    with pytest.raises(RequestError, match="You didn't say the magic word!"):
        opensearch_instance.update_index_template(template={"mappings": {}, "settings": {}})


def test_update_index_template_index_does_not_exist(caplog, opensearch_instance):
    opensearch_instance.client.indices.exists.return_value = False
    with caplog.at_level("INFO"):
        opensearch_instance.update_index_template(template={"mappings": {}, "settings": {}})

    assert "Index test-index does not exist, create it first!" in caplog.messages


def test_ensure_valid_query(mocker, opensearch_instance):
    mock_client = mocker.MagicMock()
    mocker.patch("search_gov_crawler.indexing.opensearch.OpenSearch", return_value=mock_client)
    mock_client.indices.validate_query.return_value = {"valid": True}
    assert opensearch_instance.ensure_valid_query(query='{"test": "query"}') == {"test": "query"}


def test_ensure_valid_query_invalid(opensearch_instance):
    opensearch_instance.client.indices.validate_query.return_value = {
        "valid": False,
        "error": "ParsingException[request does not support [invalid]]",
        "explanations": [
            {
                "index": "test-index",
                "valid": False,
                "explanation": "This query is really bad!",
            },
            {
                "index": "test-index",
                "valid": False,
                "explanation": "Also, its not really even a query.",
            },
        ],
    }

    expected_msg = (
        "Invalid query! Error: ParsingException[request does not support [invalid]] "
        "This query is really bad! "
        "Also, its not really even a query."
    )
    with pytest.raises(ValueError, match=re.escape(expected_msg)):
        opensearch_instance.ensure_valid_query(query='{"invalid": "query"}')


def test_ensure_valid_query_not_a_dict(mocker, opensearch_instance):
    mocker.patch("ast.literal_eval", return_value=False)
    with pytest.raises(TypeError, match=re.escape("Query input is not a valid dictionary!")):
        opensearch_instance.ensure_valid_query(query='{"invalid": "query"}')


def test_ensure_valid_query_missing_index(opensearch_instance):
    opensearch_instance.client.indices.validate_query.side_effect = [NotFoundError, {"valid": True}]
    assert opensearch_instance.ensure_valid_query(query='{"test": "query"}') == {"test": "query"}


@pytest.mark.parametrize(
    "query", [{"test": "query"}, {"test": "query", "size": 100}, {"test": "query", "size": 100, "sort": "field"}]
)
def test_count(opensearch_instance, query):
    opensearch_instance.client.count.return_value = {"count": 10}
    assert opensearch_instance.count(query=query) == 10


@pytest.fixture
def expected_matching_documents():
    return [{"document": "value"}, {"document": "value"}, {"document": "value"}]


def test_scroll(mocker, opensearch_instance, expected_matching_documents):
    def yield_results(*_args, **_kwargs):
        yield from expected_matching_documents

    mocker.patch("search_gov_crawler.indexing.opensearch.helpers.scan", side_effect=yield_results)
    assert list(opensearch_instance.scroll(query={"test": "query"}, scroll="24h")) == expected_matching_documents


def test_search(opensearch_instance):
    opensearch_instance.client.search.return_value = {
        "hits": {"hits": [{"document": "value"}, {"document": "value"}, {"document": "value"}]}
    }

    assert len(list(opensearch_instance.search(query={"test": "query"}))) == 3
