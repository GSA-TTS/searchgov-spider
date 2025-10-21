import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from pymysql import connect
from pymysql.connections import Connection
from pymysql.cursors import DictCursor


@contextmanager
def get_database_connection() -> Generator[Connection, Any, None]:
    """Returns a pymysql Connection to the given database."""

    try:
        connection_args = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "database": os.getenv("DB_NAME", "usasearch_development"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.environ["DB_PASSWORD"],
            "cursorclass": DictCursor,
            "charset": "utf8mb4",
        }
    except KeyError as e:
        msg = "DB_PASSWORD environment variable must be set"
        raise ValueError(msg) from e

    connection = connect(**connection_args)
    try:
        yield connection
    finally:
        connection.close()


def select_active_crawl_configs(connection: Connection) -> list[dict]:
    """Returns all active crawl configurations from the database."""
    stmt = """SELECT CONCAT(name,'-',id) AS name,
                     allowed_domains,
                     starting_urls,
                     sitemap_urls,
                     deny_paths,
                     depth_limit,
                     sitemap_check_hours AS check_sitemap_hours,
                     allow_query_string,
                     handle_javascript,
                     schedule,
                     output_target
              FROM   crawl_configs
              WHERE  active = 1"""

    with connection.cursor() as cursor:
        cursor.execute(stmt)
        return list(cursor.fetchall())
