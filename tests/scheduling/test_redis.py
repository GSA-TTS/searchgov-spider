from tests.scheduling.conftest import MockRedisClient
from search_gov_crawler.scheduling.redis import get_redis_connection_args, init_redis_client

import redis


def test_get_redis_connection_args_default(monkeypatch):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PORT", raising=False)

    assert get_redis_connection_args() == {
        "host": "localhost",
        "port": 6379,
        "db": 1,
    }


def test_get_redis_connection_args_custom(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "test-host")
    monkeypatch.setenv("REDIS_PORT", "1234")

    assert get_redis_connection_args() == {
        "host": "test-host",
        "port": 1234,
        "db": 1,
    }


def test_init_redis_client(monkeypatch):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PORT", raising=False)

    def mock_redis(*_args, **_kwargs):
        return MockRedisClient()

    monkeypatch.setattr("search_gov_crawler.scheduling.redis.Redis", mock_redis)
    assert isinstance(init_redis_client(), MockRedisClient)
