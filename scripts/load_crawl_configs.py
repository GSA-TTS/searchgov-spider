import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from search_gov_crawler.search_gov_app.database import get_database_connection

load_dotenv()

CRAWL_SITES_FILE = (
    Path(__file__).parent / "domains" / os.environ.get("SPIDER_CRAWL_SITES_FILE_NAME", "crawl-sites-production.json")
)


def load_crawl_config(input_file: str | None, *, truncate_table: bool = False) -> None:
    """Load crawl config table from the provided JSON file into the database"""

    crawl_sites_file = Path(input_file).resolve() if input_file else CRAWL_SITES_FILE

    with crawl_sites_file.open(encoding="UTF-8") as f:
        records = json.load(f)

    for record in records:
        record["output_target"] = (
            "searchengine" if record["output_target"] == "elasticsearch" else record["output_target"]
        )
        record["sitemap_urls"] = json.dumps(record["sitemap_urls"]) if record["sitemap_urls"] else "[]"
        record["deny_paths"] = json.dumps(record["deny_paths"]) if record["deny_paths"] else "[]"
        record["starting_urls"] = json.dumps(record["starting_urls"].split(",")) if record["starting_urls"] else "[]"
        record["allowed_domains"] = (
            json.dumps(record["allowed_domains"].split(",")) if record["allowed_domains"] else "[]"
        )

    print(f"Found {len(records)} records in {crawl_sites_file}")

    with get_database_connection() as connection, connection.cursor() as cursor:
        if truncate_table:
            cursor.execute("TRUNCATE TABLE crawl_configs")
            print("Truncated crawl_configs table")

        cursor.executemany(
            """INSERT INTO crawl_configs
                      (name, allowed_domains, starting_urls, sitemap_urls, deny_paths, depth_limit, sitemap_check_hours,
                       allow_query_string, handle_javascript, schedule, output_target, created_at, updated_at
                      )
               VALUES (%(name)s, %(allowed_domains)s, %(starting_urls)s, %(sitemap_urls)s, %(deny_paths)s,
                       %(depth_limit)s, %(check_sitemap_hours)s, %(allow_query_string)s, %(handle_javascript)s,
                       %(schedule)s, %(output_target)s, NOW(), NOW()
                     )""",
            records,
        )

        connection.commit()
        print(f"Inserted {len(records)} records into crawl_configs table")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load crawl config data into the database")
    parser.add_argument(
        "--input_file",
        help="Path to JSON file with crawl config data, default is SPIDER_CRAWL_SITES_FILE_NAME env var",
    )
    parser.add_argument("--truncate_table", action="store_true", help="Truncate the crawl_configs table before loading")
    args = parser.parse_args()

    load_crawl_config(input_file=args.input_file, truncate_table=args.truncate_table)
