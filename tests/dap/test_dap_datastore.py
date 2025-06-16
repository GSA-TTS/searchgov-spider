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

    mocked_redis_client = mocker.Mock()
    write_dap_record_to_redis(mocked_redis_client, domain, date, visits)
    mocked_redis_client.zadd.assert_called_once_with("dap_visits:example.com", {"100": 20250521})


@freeze_time("2025-05-21 00:00:00", tz_offset=0)
def test_age_off_dap_records(mocker):
    age_off_records_per_key = 10
    expected_age_off_records = 20

    mocked_redis_client = mocker.Mock()
    mocked_redis_client.keys.return_value = ["dap_visits:example.com", "dap_visits:example2.com"]
    mocked_redis_client.zremrangebyscore.return_value = age_off_records_per_key

    records_aged_off = age_off_dap_records(mocked_redis_client, age_off_records_per_key)

    # assert
    calls = [
        mocker.call(name="dap_visits:example.com", min="-inf", max=20250511),
        mocker.call(name="dap_visits:example2.com", min="-inf", max=20250511),
    ]
    mocked_redis_client.zremrangebyscore.assert_has_calls(calls)
    assert records_aged_off == expected_age_off_records


def test_get_avg_daily_visits_by_domain(mocker):
    mocked_redis_client = mocker.Mock()
    mocked_redis_client.keys.side_effect = [
        ["dap_visits:example.com", "dap_visits:test1.example.com"],
        ["dap_visits:test2.example.com", "dap_visits:test3.example.com"],
    ]
    mocked_redis_client.zrangebyscore.side_effect = [
        list(range(10, 110, 10)),
        list(range(11, 111, 10)),
        list(range(12, 112, 10)),
        list(range(13, 113, 10)),
    ]

    result = get_avg_daily_visits_by_domain(mocked_redis_client, "example.com", 10)

    assert result == {
        "example.com": 55.0,
        "test1.example.com": 56.0,
        "test2.example.com": 57.0,
        "test3.example.com": 58.0,
    }
