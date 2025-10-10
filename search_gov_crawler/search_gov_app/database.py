import os

from pymysql import connect
from pymysql.connections import Connection
from pymysql.cursors import DictCursor


def get_database_connection() -> Connection:
    """Returns a pymysql Connection to the given database."""
    return connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "usasearch_development"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        cursorclass=DictCursor,
    )
