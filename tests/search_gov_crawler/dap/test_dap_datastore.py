import pytest
from freezegun import freeze_time

from search_gov_crawler.dap.datastore import (
    age_off_dap_records,
    get_avg_daily_visits_by_domain,
    write_dap_record_to_redis,
)


def test_write_dap_record_to_redis(mocker):
    domain = "example.com"
    date = "2025-05-21"
    visits = 100

    mock_redis_client = mocker.Mock()
    write_dap_record_to_redis(mock_redis_client, domain, date, visits)
    mock_redis_client.zadd.assert_called_once_with("dap_visits:example.com", {"100": 20250521})


@freeze_time("2025-05-21 00:00:00", tz_offset=0)
def test_age_off_dap_records(mocker):
    age_off_records_per_key = 10
    expected_age_off_records = 20

    mock_redis_client = mocker.Mock()
    mock_redis_client.scan_iter.return_value = ["dap_visits:example.com", "dap_visits:example2.com"]
    mock_redis_client.pipeline.return_value.execute.return_value = [10, 10]

    records_aged_off = age_off_dap_records(mock_redis_client, age_off_records_per_key)

    # assert
    calls = [
        mocker.call(name="dap_visits:example.com", min="-inf", max=20250511),
        mocker.call(name="dap_visits:example2.com", min="-inf", max=20250511),
    ]
    mock_redis_client.pipeline.return_value.zremrangebyscore.assert_has_calls(calls)
    assert records_aged_off == expected_age_off_records


def test_get_avg_daily_visits_by_domain(mocker):
    mock_redis_client = mocker.Mock()
    mock_redis_client.scan_iter.side_effect = [
        [b"dap_visits:example.com", b"dap_visits:test1.example.com"],
        [b"dap_visits:test2.example.com", b"dap_visits:test3.example.com"],
    ]
    mock_redis_client.pipeline.return_value.execute.return_value = [
        list(range(10, 110, 10)),
        list(range(11, 111, 10)),
        list(range(12, 112, 10)),
        list(range(13, 113, 10)),
    ]

    result = get_avg_daily_visits_by_domain(mock_redis_client, "example.com", 10)

    assert result == {
        "example.com": 55,
        "test1.example.com": 56,
        "test2.example.com": 57,
        "test3.example.com": 58,
    }


def test_get_avg_daily_visits_by_domain_invalid_results(caplog, mocker):
    mock_redis_client = mocker.Mock()
    mock_redis_client.scan_iter.side_effect = [
        [b"dap_visits:example.com", b"dap_visits:test1.example.com"],
        [b"dap_visits:test2.example.com", b"dap_visits:test3.example.com"],
    ]
    mock_redis_client.pipeline.return_value.execute.return_value = [list(range(10, 110, 10))]

    error_msg = "Cannot get avg daily visits.  Invalid response from redis pipeline.  Expceted: 4, Got: 1"
    with caplog.at_level("ERROR"):
        result = get_avg_daily_visits_by_domain(mock_redis_client, "example.com", 10)

    assert error_msg in caplog.messages
    assert not result
