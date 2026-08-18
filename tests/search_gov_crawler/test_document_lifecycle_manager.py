import pytest

from search_gov_crawler.config.settings import SearchgovSettings
from search_gov_crawler.document_lifecycle_manager import main, process_deletion_batch, run_stale_document_deletion

PROCESS_DELETION_BATCH_TEST_CASES = [
    (
        [
            {"delete": {"_index": "test-index", "_id": "1234", "result": "deleted", "status": 200}},
            {"delete": {"_index": "test-index", "_id": "2345", "result": "deleted", "status": 200}},
            {"delete": {"_index": "test-index", "_id": "3456", "result": "deleted", "status": 200}},
            {"delete": {"_index": "test-index", "_id": "4567", "result": "deleted", "status": 200}},
            {"delete": {"_index": "test-index", "_id": "5678", "result": "deleted", "status": 200}},
        ],
        [
            {"delete": {"_index": "test-index", "_id": "6789", "result": "not_found", "status": 404}},
            {
                "delete": {
                    "_index": "test-index",
                    "_id": "7890",
                    "result": "server_error",
                    "status": 500,
                    "errror": {"type": "internal_server_error", "reason": "server not responding"},
                }
            },
        ],
        {
            "1234": "https://delete.example.com/1",
            "5678": "https://delete.example.com/5",
            "6789": "https://error.example.com/1",
        },
        5,
        2,
    )
]


@pytest.mark.parametrize(
    ("deletions", "failures", "urls", "expected_deletions", "expected_failures"), PROCESS_DELETION_BATCH_TEST_CASES
)
def test_process_deletion_batch(caplog, mocker, deletions, failures, urls, expected_deletions, expected_failures):
    mock_opensearch = mocker.MagicMock()
    mock_opensearch.bulk_batch_upload.return_value = (deletions, failures)
    with caplog.at_level("INFO"):
        batch_deletions, batch_failures = process_deletion_batch(
            opensearch=mock_opensearch, actions=["test"], urls=urls
        )

    assert len(batch_deletions) == expected_deletions
    assert len([record for record in caplog.records if record.levelname == "INFO"]) == expected_deletions

    assert len(batch_failures) == expected_failures
    assert len([record for record in caplog.records if record.levelname == "ERROR"]) == expected_failures


@pytest.fixture
def mock_opensearch(mocker):
    return mocker.patch("search_gov_crawler.document_lifecycle_manager.SearchGovOpensearch")


@pytest.fixture
def mock_count_documents(mocker):
    return mocker.patch("search_gov_crawler.document_lifecycle_manager.count_matching_documents")


@pytest.fixture
def mock_matching_documents(mocker):
    def _create_mock(document_count):
        matching_documents = mocker.patch("search_gov_crawler.document_lifecycle_manager.get_matching_documents")

        def mock_get_matching_docs(document_count, *_args, **_kwargs):
            docs = [
                {"_id": str(i), "_source": {"field": "value", "id": str(i), "path": f"https://www.example.com/{i}"}}
                for i in range(document_count)
            ]
            yield docs

        matching_documents.side_effect = mock_get_matching_docs(document_count)

    return _create_mock


@pytest.fixture
def mock_deletion_batch(mocker):
    def _create_mock(success_count):
        mock_process_deletion_batch = mocker.patch(
            "search_gov_crawler.document_lifecycle_manager.process_deletion_batch"
        )

        def mock_get_process_deletion_batch(success_count: int):
            return [
                (
                    [
                        {"delete": {"_index": "test-search-index", "_id": str(i), "result": "deleted", "status": 200}}
                        for i in range(success_count)
                    ],
                    [],
                ),
                (
                    [
                        {
                            "delete": {
                                "_index": "test-freshness-index",
                                "_id": str(i),
                                "result": "deleted",
                                "status": 200,
                            }
                        }
                        for i in range(success_count)
                    ],
                    [],
                ),
            ]

        mock_process_deletion_batch.side_effect = mock_get_process_deletion_batch(success_count)

    return _create_mock


@pytest.mark.usefixtures("mock_opensearch")
def test_run_stale_document_deletion_no_docs_found(caplog, default_searchgov_settings, mock_count_documents):
    mock_count_documents.return_value = 0
    with caplog.at_level("INFO"):
        run_stale_document_deletion(searchgov_settings=default_searchgov_settings)

    assert "No documents found as marked for deletion! Stopping process." in caplog.messages


def test_run_stale_document_deletion(
    caplog,
    default_searchgov_settings,
    mock_opensearch,
    mock_count_documents,
    mock_matching_documents,
    mock_deletion_batch,
):
    mock_opensearch.return_value.batch_size = 10
    mock_count_documents.return_value = 5
    mock_matching_documents(5)
    mock_deletion_batch(5)

    with caplog.at_level("INFO"):
        run_stale_document_deletion(searchgov_settings=default_searchgov_settings)

    assert "Completed Stale Document Deletion! Docs Deleted: 5 Errors Encountered: 0" in caplog.messages


def test_run_stale_document_deletion_circuit_breaker(
    caplog,
    default_searchgov_settings,
    mock_opensearch,
    mock_count_documents,
    mock_matching_documents,
    mock_deletion_batch,
):
    mock_opensearch.return_value.batch_size = 5
    mock_count_documents.return_value = 10
    mock_matching_documents(10)
    mock_deletion_batch(10)

    default_searchgov_settings.dlm_max_docs = 5
    with caplog.at_level("INFO"):
        run_stale_document_deletion(searchgov_settings=default_searchgov_settings)

    assert "Circuit breaker triggered! Stopping process because next batch would exceed 5 documents." in caplog.messages


def test_document_lifecycle_manager_main(caplog, mocker):
    mock_crontrigger = mocker.patch("apscheduler.triggers.cron.CronTrigger.from_crontab")
    mock_crontrigger.return_value = True

    mock_scheduler = mocker.patch("search_gov_crawler.document_lifecycle_manager.init_singleton_job_scheduler")

    with caplog.at_level("INFO"):
        main(searchgov_settings=SearchgovSettings(dlm_schedule="*/10 * * * *"))

    assert (
        "Starting scheduler for document lifecycle manager based on crontab expression */10 * * * *" in caplog.messages
    )
    mock_scheduler.return_value.add_job.assert_called_once_with(
        func=run_stale_document_deletion,
        trigger=True,
        name="document_lifecycle_manager",
    )
    mock_scheduler.return_value.start.assert_called_once()


def test_document_lifecycle_manager_main_crontrigger_error(caplog):
    with caplog.at_level("INFO"), pytest.raises(ValueError, match="Invalid month name"):
        main(searchgov_settings=SearchgovSettings(dlm_schedule="THIS IS NOT A SCHEDULE"))

    assert "Invalid crontab expression from DLM_SCHEDULE: THIS IS NOT A SCHEDULE" in caplog.messages
