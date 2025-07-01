import asyncio

import pytest
from elasticsearch import Elasticsearch

from search_gov_crawler.elasticsearch.es_batch_upload import SearchGovElasticsearch

HTML_CONTNET = """
    <html lang="en">
    <head>
        <title>Test Article Title</title>
        <meta name="description" content="Test article description.">
        <meta name="keywords" content="test, article, keywords">
        <meta property="og:image" content="https://example.com/image.jpg">
        <meta name="lang" content="en">
    </head>
    <body>
        <h1>Test Article Title</h1>
        <p>This is the main content of the test article.</p>
    </body>
    </html>
"""

RESPONSE_BYTES = HTML_CONTNET.encode()


@pytest.fixture(name="sample_spider")
def fixture_sample_spider(mocker):
    """Fixture for a mock spider with a logger."""

    class SpiderMock:
        logger = mocker.MagicMock()

    return SpiderMock()


# Mock environment variables
@pytest.fixture(autouse=True, name="search_gov_es")
def fixture_search_gov_es(mocker):
    mocker.patch.dict(
        "os.environ",
        {
            "ES_HOSTS": "http://localhost:9200",
            "SEARCHELASTIC_INDEX": "test_index",
            "ES_USER": "test_user",
            "ES_PASSWORD": "test_password",
        },
    )
    return SearchGovElasticsearch(batch_size=2)


@pytest.fixture(name="mock_es_client")
def fixture_mock_es_client(mocker):
    client = mocker.MagicMock(spec=Elasticsearch)
    client.indices = mocker.MagicMock()
    client.indices.exists = mocker.MagicMock()
    client.indices.create = mocker.MagicMock()
    return client


# Mock convert_html function
@pytest.fixture(name="mock_convert_html")
def fixture_mock_convert_html(mocker):
    return mocker.patch("search_gov_crawler.elasticsearch.es_batch_upload.convert_html")


@pytest.fixture(name="mock_asyncio_loop")
def fixture_mock_asyncio_loop(mocker):
    mock_get_loop = mocker.patch("search_gov_crawler.elasticsearch.es_batch_upload.asyncio.get_event_loop")
    mock_loop = asyncio.new_event_loop()
    mock_get_loop.return_value = mock_loop

    mock_new_loop = mocker.patch("search_gov_crawler.elasticsearch.es_batch_upload.asyncio.new_event_loop")
    mock_new_loop.return_value = mock_loop
    yield mock_loop
    mock_loop.close()


# Test add_to_batch (Corrected)
@pytest.mark.asyncio(loop_scope="module")
async def test_add_to_batch(mocker, mock_convert_html, sample_spider):
    test_document = {"_id": "1", "title": "Test Document"}
    mock_update_dap_visits = mocker.patch(
        "search_gov_crawler.elasticsearch.es_batch_upload.update_dap_visits_to_document",
    )
    mock_update_dap_visits.return_value = test_document
    mock_convert_html.return_value = test_document

    es_uploader = SearchGovElasticsearch(batch_size=2)
    es_uploader.add_to_batch(RESPONSE_BYTES, "http://example.com/1", sample_spider, "en", "text/html")
    assert len(es_uploader._current_batch) == 1

    es_uploader.add_to_batch(RESPONSE_BYTES, "http://example.com/2", sample_spider, "en", "text/html")
    assert len(es_uploader._current_batch) == 0


@pytest.mark.asyncio(loop_scope="module")
async def test_batch_upload(mock_convert_html, sample_spider):  # Use pytest-asyncio's event loop
    es_uploader = SearchGovElasticsearch(batch_size=2)
    mock_convert_html.return_value = {"_id": "1", "title": "Test Document"}
    es_uploader._current_batch = [{"_id": "1", "title": "Test Document"}, {"_id": "2", "title": "Test Document"}]

    es_uploader.batch_upload(sample_spider)
    assert len(es_uploader._current_batch) == 0


@pytest.mark.asyncio(loop_scope="module")
async def test_batch_upload_empty(mocker, sample_spider):
    es_uploader = SearchGovElasticsearch(batch_size=2)
    es_uploader._current_batch = []
    es_uploader._batch_elasticsearch_upload = mocker.MagicMock()
    es_uploader.batch_upload(sample_spider)
    es_uploader._batch_elasticsearch_upload.assert_not_called()  # Ensure it is not called when the batch is empty


# Test _batch_elasticsearch_upload
@pytest.mark.asyncio(loop_scope="module")
async def test_batch_elasticsearch_upload(mocker, mock_convert_html, mock_asyncio_loop, sample_spider):
    es_uploader = SearchGovElasticsearch(batch_size=2)
    docs = [{"_id": "1", "title": "Test Document"}]
    mock_convert_html.return_value = docs[0]
    es_uploader._create_actions = mocker.MagicMock()
    await es_uploader._batch_elasticsearch_upload(docs, mock_asyncio_loop, sample_spider)
    es_uploader._create_actions.assert_called_once()


def test_add_to_batch_no_doc(mock_convert_html, sample_spider):
    es_uploader = SearchGovElasticsearch(batch_size=2)
    mock_convert_html.return_value = None

    es_uploader.add_to_batch(b"<html></html>", "http://example.com/1", sample_spider, "en", "text/html")
    assert len(es_uploader._current_batch) == 0


def test_parse_es_urls_invalid_url():
    es_uploader = SearchGovElasticsearch()
    with pytest.raises(ValueError) as excinfo:
        es_uploader._parse_es_urls("invalid-url")
    assert "Invalid Elasticsearch URL" in str(excinfo.value)


def test_parse_es_urls_valid_urls():
    es_uploader = SearchGovElasticsearch()
    hosts = es_uploader._parse_es_urls("http://localhost:9200,https://remotehost:9300")
    assert hosts == [
        {"host": "localhost", "port": 9200, "scheme": "http"},
        {"host": "remotehost", "port": 9300, "scheme": "https"},
    ]


def test_get_client(mocker, search_gov_es, mock_es_client):
    mock_es = mocker.patch("search_gov_crawler.elasticsearch.es_batch_upload.Elasticsearch")
    mock_es.return_value = mock_es_client

    client = search_gov_es._get_client()
    assert client == mock_es_client
    assert search_gov_es._es_client == mock_es_client


def test_get_client_exception(mocker, search_gov_es):
    mock_es = mocker.patch("search_gov_crawler.elasticsearch.es_batch_upload.Elasticsearch")
    mock_es.side_effect = Exception("Test Exception")
    mock_log = mocker.patch("search_gov_crawler.elasticsearch.es_batch_upload.log")

    client = search_gov_es._get_client()
    assert client is None
    mock_log.exception.assert_called_once()


def test_create_actions(search_gov_es):
    docs = [{"_id": "1", "content": "test1"}, {"_id": "2", "content": "test2"}]
    actions = search_gov_es._create_actions(docs)
    assert actions == [
        {"_index": "test_index", "_id": "1", "_source": {"content": "test1"}},
        {"_index": "test_index", "_id": "2", "_source": {"content": "test2"}},
    ]


@pytest.mark.asyncio
async def test_batch_elasticsearch_upload_error(mocker, search_gov_es, sample_spider, mock_es_client):
    mock_es = mocker.patch("search_gov_crawler.elasticsearch.es_batch_upload.SearchGovElasticsearch._get_client")
    mock_es.return_value = mock_es_client

    mock_bulk = mocker.patch("search_gov_crawler.elasticsearch.es_batch_upload.helpers.bulk")
    mock_bulk.return_value = (49, [{"error": "Test Error"}])

    docs = [{"_id": "1", "content": "test1"}, {"_id": "2", "content": "test2"}]
    loop = asyncio.get_event_loop()
    await search_gov_es._batch_elasticsearch_upload(docs, loop, sample_spider)
    sample_spider.logger.error.assert_called_once()  # logged errors from bulk_upload
    sample_spider.logger.exception.assert_not_called()  # did not log and exception


def test_client_property(mocker, search_gov_es, mock_es_client):
    mock_es = mocker.patch("search_gov_crawler.elasticsearch.es_batch_upload.Elasticsearch")
    mock_es.return_value = mock_es_client
    assert search_gov_es.client == mock_es_client


def test_index_name_property(search_gov_es):
    assert search_gov_es.index_name == "test_index"
