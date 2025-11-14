import pytest
from pymysql.cursors import DictCursor

from search_gov_crawler.search_gov_app.database import get_database_connection, select_active_crawl_configs


class MockCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return True

    @staticmethod
    def execute(*_args, **_kwargs):
        return True

    @staticmethod
    def fetchall():
        return ["test_record", "test_record_2"]


class MockConnection:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def close(self):
        return True

    def cursor(self, **_kwargs):
        return MockCursor()


def test_get_database_connection_missing_password(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="DB_PASSWORD environment variable must be set"):
        get_database_connection().__enter__()


def test_get_database_connection(monkeypatch):
    monkeypatch.setenv("DB_HOST", "test_host")
    monkeypatch.setenv("DB_PORT", "1234")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")

    def mock_connect(**kwargs):
        return MockConnection(**kwargs)

    monkeypatch.setattr("search_gov_crawler.search_gov_app.database.connect", mock_connect)

    with get_database_connection() as connection:
        assert connection.kwargs == {
            "host": "test_host",
            "port": 1234,
            "database": "test_db",
            "user": "test_user",
            "password": "test_password",
            "cursorclass": DictCursor,
            "charset": "utf8mb4",
        }


def test_select_active_crawl_configs():
    connection = MockConnection()
    results = select_active_crawl_configs(connection)
    assert results == ["test_record", "test_record_2"]
