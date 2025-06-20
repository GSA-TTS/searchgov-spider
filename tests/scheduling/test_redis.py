import pytest

from search_gov_crawler.scheduling.redis import get_redis_connection_args, init_redis_client


@pytest.fixture(name="clear_redis_env_vars")
def fixture_clear_redis_env_vars(monkeypatch):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PORT", raising=False)


@pytest.fixture(name="set_redis_env_vars")
def fixture_set_redis_env_vars(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "test-host")
    monkeypatch.setenv("REDIS_PORT", "1234")


@pytest.mark.usefixtures("clear_redis_env_vars")
def test_get_redis_connection_args_default():
    assert get_redis_connection_args() == {
        "host": "localhost",
        "port": 6379,
        "db": 1,
    }


@pytest.mark.usefixtures("set_redis_env_vars")
def test_get_redis_connection_args_custom():
    assert get_redis_connection_args() == {
        "host": "test-host",
        "port": 1234,
        "db": 1,
    }


@pytest.mark.usefixtures("clear_redis_env_vars")
def test_get_redis_connection_db_arg():
    assert get_redis_connection_args(db=100) == {
        "host": "localhost",
        "port": 6379,
        "db": 100,
    }


@pytest.mark.usefixtures("set_redis_env_vars")
def test_init_redis_client(monkeypatch, mock_redis_client):
    def mock_redis(*_args, **_kwargs):
        return mock_redis_client

    monkeypatch.setattr("search_gov_crawler.scheduling.redis.Redis", mock_redis)
    assert init_redis_client().ping()
