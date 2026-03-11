import pytest
from click.testing import CliRunner
from elastic_transport import ApiResponseMeta
from elasticsearch import NotFoundError
from opensearchpy.exceptions import RequestError

from scripts import transfer_docs as td


def test_count_matching_documents(mocker):
    mock_sg_elastic = mocker.MagicMock()
    mock_sg_elastic.client.count.return_value = {"count": 100}

    count = td.count_matching_documents(es=mock_sg_elastic, query={"some": "query"})
    assert count == 100


def test_get_matching_documents(mocker):
    mock_sg_elastic = mocker.MagicMock()

    mock_scan = mocker.patch("scripts.transfer_docs.scan")
    mock_scan.return_value = [
        {"_id": "1", "_source": {"field": "value1"}},
        {"_id": "2", "_source": {"field": "value2"}},
    ]

    documents = list(td.get_matching_documents(es=mock_sg_elastic, query={"some": "query"}, scroll="1m"))
    assert len(documents) == 2
    assert documents[0]["_id"] == "1"
    assert documents[0]["_source"]["field"] == "value1"
    assert documents[1]["_id"] == "2"
    assert documents[1]["_source"]["field"] == "value2"


def test_create_opensearch_action():
    document = {
        "_id": "asdf",
        "_source": {
            "id": "1234",
            "data": "value",
        },
        "_index": "test-source-index",
    }
    index = "test-target-index"

    action = td.create_opensearch_action(document=document, target_index=index)
    assert action == {
        "_index": "test-target-index",
        "_id": "1234",
        "_source": {
            "id": "1234",
            "data": "value",
        },
    }


def test_transform_es_template():
    es_template = {
        "index_patterns": ["*test*"],
        "settings": {"setting 1": "value 1"},
        "mappings": {"field": "mapping value"},
    }
    os_template = td.transform_es_template(es_template)

    assert os_template == {
        "index_patterns": ["*test*"],
        "template": {"settings": {"setting 1": "value 1"}, "mappings": {"field": "mapping value"}},
    }


def test_create_opensearch_target(mocker):
    mock_es = mocker.MagicMock()
    mock_os = mocker.MagicMock()

    mocker.patch("scripts.transfer_docs.transform_es_template")

    mock_get_template = mock_es.client.indices.get_template
    mock_put_template = mock_os.client.indices.put_index_template
    mock_create = mock_os.client.indices.create

    td.create_opensearch_target(mock_es, mock_os)

    mock_get_template.assert_called_once()
    mock_put_template.assert_called_once()
    mock_create.assert_called_once()


def test_create_opensearch_target_index_not_found(mocker):
    mock_es = mocker.MagicMock()
    mock_os = mocker.MagicMock()

    meta = mocker.Mock(spec=ApiResponseMeta)
    meta.status = 404
    body = {"error": "Not Found", "status": 404}

    mock_es.client.indices.get_template.side_effect = [
        NotFoundError(message="Document not found", meta=meta, body=body)
    ]

    with pytest.raises(NotFoundError, match="Document not found"):
        td.create_opensearch_target(mock_es, mock_os)


def test_create_opensearch_target_index_already_exists(mocker):
    mock_es = mocker.MagicMock()
    mock_os = mocker.MagicMock()
    mock_os.client.indices.create.side_effect = [RequestError(400, "Index already exists!")]

    with pytest.raises(RequestError, match="Index already exists!"):
        td.create_opensearch_target(mock_es, mock_os)


def test_generate_docs_from_elasticsearch(mocker):
    mock_es = mocker.MagicMock()

    test_docs = [
        {"_id": "123", "_source": {"data": "here"}},
        {"_id": "456", "_source": {"data": "here"}},
    ]

    mock_count_docs = mocker.patch("scripts.transfer_docs.count_matching_documents")
    mock_count_docs.return_value = 2

    mocker.patch("scripts.transfer_docs.get_matching_documents", return_value=test_docs)
    mocker.patch("scripts.transfer_docs.create_opensearch_action", return_value=test_docs)

    output = list(td.generate_docs_from_elasticsearch(mock_es, "test-index", "10m"))
    assert len(output) == len(test_docs)


def test_generate_docs_from_elasticsearch_no_docs(mocker, caplog):
    mock_es = mocker.MagicMock()

    mock_count_docs = mocker.patch("scripts.transfer_docs.count_matching_documents")
    mock_count_docs.return_value = 0

    with caplog.at_level("INFO"):
        output = list(td.generate_docs_from_elasticsearch(mock_es, "test-index", "10m"))

    assert not output
    assert "No documents found! Check query and try again!" in caplog.messages


def test_generate_docs_from_elasticsearch_doc_error(mocker, caplog):
    mock_es = mocker.MagicMock()

    test_docs = [
        {"_id": "123", "_source": {"data": "here"}},
        {"_id": "456", "_source": {"data": "here"}},
    ]

    mock_count_docs = mocker.patch("scripts.transfer_docs.count_matching_documents")
    mock_count_docs.return_value = 2

    mocker.patch("scripts.transfer_docs.get_matching_documents", return_value=test_docs)
    mocker.patch(
        "scripts.transfer_docs.create_opensearch_action",
        side_effect=[Exception("Error here!"), Exception("Error here!")],
    )

    with caplog.at_level("INFO"):
        output = list(td.generate_docs_from_elasticsearch(mock_es, "test-index", "10m"))

    assert not output
    assert all(
        message in caplog.messages for message in ["Error processing document 123", "Error processing document 456"]
    )


VALIDATE_ARGS_TEST_CASES = [
    (None, None, ("development-i14y-documents-searchgov-legacy", "development-i14y-documents-searchgov-legacy")),
    ("test1", None, ("test1", "test1")),
    ("test1", "test2", ("test1", "test2")),
]


@pytest.mark.parametrize(("source", "target", "output"), VALIDATE_ARGS_TEST_CASES)
def test_validate_args(monkeypatch, source, target, output):
    monkeypatch.delenv("LEGACY_OPENSEARCH_INDEX", raising=False)
    assert output == td.validate_args(source, target)


def test_validate_args_env(monkeypatch):
    monkeypatch.setenv("LEGACY_OPENSEARCH_INDEX", "test-env")
    assert td.validate_args(None, None) == ("test-env", "test-env")


@pytest.mark.parametrize(
    ("args", "log_msgs"),
    [
        ([], ["Finished loading documents!", "There were 100 errors:", "Whoops!"]),
        (
            ["--create-target"],
            [
                "Finished loading documents!",
                "There were 100 errors:",
                "Whoops!",
                "Creating target template and index...",
            ],
        ),
    ],
)
def test_copy_index(mocker, caplog, args, log_msgs):
    mocker.patch("scripts.transfer_docs.create_opensearch_target")
    mocker.patch("scripts.transfer_docs.validate_args", return_value=("source", "target"))
    mocker.patch("scripts.transfer_docs.SearchGovElasticsearch")
    mock_os = mocker.patch("scripts.transfer_docs.SearchGovOpensearch")
    mock_os.sg_os.client.indices.exists.return_value = True

    mock_streaming_bulk = mocker.patch("scripts.transfer_docs.streaming_bulk")
    mock_streaming_bulk.return_value = [
        (True, {"result": "Success"}),
        (True, {"result": "Success"}),
        (False, {"index": {"error": "Whoops!"}}),
        (True, {"result": "Success"}),
        (True, {"result": "Success"}),
    ] * 100
    runner = CliRunner()
    with caplog.at_level("INFO"):
        runner.invoke(td.copy_index, args)

    assert all(message in caplog.messages for message in log_msgs)


def test_copy_index_no_source_index(mocker):
    mock_es = mocker.patch("scripts.transfer_docs.SearchGovElasticsearch")
    mock_es.return_value.client.indices.exists.return_value = False
    mocker.patch("scripts.transfer_docs.SearchGovOpensearch")

    runner = CliRunner()
    result = runner.invoke(td.copy_index)
    assert result.exception is not None
    assert isinstance(result.exception, Exception)
    assert str(result.exception) == "Source Index Doesn't Exist!"


def test_copy_no_target_index(mocker):
    mocker.patch("scripts.transfer_docs.SearchGovElasticsearch")
    mock_os = mocker.patch("scripts.transfer_docs.SearchGovOpensearch")
    mock_os.return_value.client.indices.exists.return_value = False

    runner = CliRunner()
    result = runner.invoke(td.copy_index)
    assert result.exception is not None
    assert isinstance(result.exception, RequestError)
    assert "Index does not exist!" in str(result.exception)
