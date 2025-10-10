from pymysql.cursors import DictCursor

from search_gov_crawler.search_gov_app.database import get_database_connection


class MockConnection:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_get_database_connection(monkeypatch):
    monkeypatch.setenv("DB_HOST", "test_host")
    monkeypatch.setenv("DB_PORT", "1234")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")

    def mock_connect(**kwargs):
        return MockConnection(**kwargs)

    monkeypatch.setattr("search_gov_crawler.search_gov_app.database.connect", mock_connect)
    connection = get_database_connection()
    assert connection.kwargs == {
        "host": "test_host",
        "port": 1234,
        "database": "test_db",
        "user": "test_user",
        "password": "test_password",
        "cursorclass": DictCursor,
    }
