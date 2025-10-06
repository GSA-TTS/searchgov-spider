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


def select_active_crawl_configs(connection: Connection) -> list[dict]:
    """Returns all active crawl configurations from the database."""
    stmt = """SELECT id,
                     name,
                     allowed_domains,
                     starting_urls,
                     sitemap_urls,
                     deny_paths,
                     depth_limit,
                     sitemap_check_hours,
                     allow_query_string,
                     handle_javascript,
                     schedule,
                     output_target
              FROM   crawl_configs
              WHERE  active = 1"""

    with connection.cursor() as cursor:
        cursor.execute(stmt)
        return list(cursor.fetchall())
