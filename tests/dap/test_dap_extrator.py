import pytest
from freezegun import freeze_time

from search_gov_crawler.dap_extractor import main, run_dap_extractor


def test_dap_extractor_main(caplog, monkeypatch, mocker):
    monkeypatch.setenv("DAP_EXTRACTOR_SCHEDULE", "*/10 * * * *")
    mock_crontrigger = mocker.patch("apscheduler.triggers.cron.CronTrigger.from_crontab")
    mock_crontrigger.return_value = True

    mock_scheduler = mocker.patch("search_gov_crawler.dap_extractor.init_scheduler")

    with caplog.at_level("INFO"):
        main(10, 10)

    assert "Starting scheduler for dap extractor based on crontab expression */10 * * * *" in caplog.messages
    mock_scheduler.return_value.add_job.assert_called_once_with(
        func=run_dap_extractor,
        trigger=True,
        args=(10, 10),
        name="dap_extractor",
    )
    mock_scheduler.return_value.start.assert_called_once()


def test_dap_extractor_main_crontrigger_error(caplog, monkeypatch):
    monkeypatch.setenv("DAP_EXTRACTOR_SCHEDULE", "THIS IS NOT A SCHEDULE")

    with caplog.at_level("INFO"), pytest.raises(ValueError, match="Invalid month name"):
        main(10, 10)

    assert "Invalid crontab expression from in DAP_EXTRACTOR_SCHEDULE!" in caplog.messages


@freeze_time("2025-05-21 01:23:34", tz_offset=0)
def test_run_dap_extractor(caplog, mocker):
    mocker.patch("search_gov_crawler.dap_extractor.Redis")

    mock_get_dap_page_by_date = mocker.patch("search_gov_crawler.dap_extractor.get_dap_page_by_date")
    mock_get_dap_page_by_date.side_effect = [
        [{"data": "data"}, {"data": "data"}],
        [{"data": "data"}, {"data": "data"}],
        [],
        [{"data": "data"}, {"data": "data"}],
        [{"data": "data"}, {"data": "data"}],
        [],
    ]
    mock_transform_dap_response = mocker.patch("search_gov_crawler.dap_extractor.transform_dap_response")
    mock_transform_dap_response.return_value = [{"data": "data"}, {"data": "data"}, {"data": "data"}, {"data": "data"}]

    mocker.patch("search_gov_crawler.dap_extractor.write_dap_record_to_redis")
    mock_age_off_dap_records = mocker.patch("search_gov_crawler.dap_extractor.age_off_dap_records")
    mock_age_off_dap_records.return_value = 10

    with caplog.at_level("INFO"):
        run_dap_extractor(2, 2)

    expected_log_messages = (
        "Fetched 4 records fetched from DAP for date: 2025-05-20",
        "Wrote 4 records to Redis for date: 2025-05-20",
        "Fetched 4 records fetched from DAP for date: 2025-05-19",
        "Wrote 4 records to Redis for date: 2025-05-19",
        "Aged off 10 records older than 2 days",
    )
    assert all(msg in caplog.messages for msg in expected_log_messages)
