# ruff: noqa: T201
"""
Helper script to assist with testing.  This can be used to load test documents into either the
search index or the freshness index you have defined in your environment.  These indices must
already exist prior to trying to load test docs.

For the search index you can load a variable number of docs for each day passed as arguments. This
script will that number of documents in the proper search format and index them.  This helps load
the search index and can be used if you want data but don't care about the domains or actual content.

For the freshness index you can select a number of docs from the search indx that you want to use
to create freshness documents that are marked for deletion. This can be used to test the document
deletion process.

Use `--help` on the CLI to see all options and arguments
"""

import argparse
import hashlib
from datetime import UTC, datetime, timedelta

from faker import Faker

from search_gov_crawler.config.settings import SearchgovSettings
from search_gov_crawler.indexing.opensearch import SearchGovOpensearch
from search_gov_crawler.search_gov_spiders.items import FreshnessSpiderItem

searchgov_settings = SearchgovSettings()


def index_check(*index_names: str, opensearch: SearchGovOpensearch):
    for index_name in index_names:
        if not opensearch.index_exists(index_name=index_name):
            msg = (
                f"Index {index_name} does not exist! Test Document Load cannot continue. "
                "Create index using normal process and rerun."
            )
            raise ValueError(msg)


def generate_fake_freshness_documents(opensearch: SearchGovOpensearch, search_docs: int):
    """
    Generate fake freshness documents based actual search docs
    """
    if search_docs > 10000:
        print(f"Size argument cannot be larger than 10,000: {search_docs=}")
        return []

    results = opensearch.client.search(
        body={"query": {"match_all": {}}, "size": search_docs, "sort": [{"updated_at": {"order": "asc"}}]},
        index=opensearch.searchgov_settings.opensearch_search_index,
    )
    return [
        FreshnessSpiderItem(
            checked_at=datetime.now(tz=UTC),
            result="404",
            marked_for_deletion=True,
            status_code="404",
            exception=None,
            index_name=doc["_index"],
            id=doc["_id"],
            path=doc["_source"]["path"],
            domain_name=doc["_source"]["path"],
        ).to_dict()
        for doc in results["hits"]["hits"]
    ]


def generate_fake_documents(from_date: str, to_date: str, docs_per_day: int) -> list[dict]:
    """
    Generate fake documents with updated_at dates spread across the date range.

    Args:
        from_date: Start date in format "YYYY-MM-DD"
        to_date: End date in format "YYYY-MM-DD"
        docs_per_day: Number of documents to generate per day

    Returns:
        List of document dictionaries
    """
    fake = Faker()

    start_date = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=UTC)
    end_date = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=UTC)

    documents = []
    current_date = start_date

    while current_date <= end_date:
        for _ in range(docs_per_day):
            random_time = current_date.replace(
                hour=fake.random_int(0, 23), minute=fake.random_int(0, 59), second=fake.random_int(0, 59), microsecond=0
            )

            updated_at = random_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            created_at = (random_time - timedelta(days=fake.random_int(1, 30))).strftime("%Y-%m-%dT%H:%M:%SZ")
            changed_date = (random_time - timedelta(days=fake.random_int(0, 7))).strftime("%Y-%m-%dT%H:%M:%SZ")
            updated_date = (random_time - timedelta(days=fake.random_int(0, 3))).strftime("%Y-%m-%dT%H:%M:%SZ")

            doc_id = hashlib.sha256(f"{fake.uuid4()}".encode()).hexdigest()

            url = fake.url()
            path = fake.uri_path()
            basename = fake.file_name()
            extension = fake.file_extension()

            doc = {
                "audience": fake.random_element(["public", "internal", "restricted"]),
                "changed": changed_date,
                "click_count": None,
                "content_type": "article",
                "created_at": created_at,
                "created": None,
                "id": doc_id,
                "thumbnail_url": fake.image_url() if fake.boolean() else None,
                "language": fake.random_element(["en", "es", "fr", "de"]),
                "mime_type": "text/html",
                "path": url,
                "promote": None,
                "searchgov_custom1": None,
                "searchgov_custom2": None,
                "searchgov_custom3": None,
                "tags": [fake.word() for _ in range(fake.random_int(1, 5))],
                "updated_at": updated_at,
                "updated": updated_date,
                "title": fake.sentence(nb_words=6),
                "title_en": fake.sentence(nb_words=6),
                "description": fake.paragraph(nb_sentences=3),
                "description_en": fake.paragraph(nb_sentences=3),
                "content": fake.paragraph(nb_sentences=fake.random_int(5, 15)),
                "content_en": fake.paragraph(nb_sentences=fake.random_int(5, 15)),
                "basename": basename,
                "extension": extension,
                "url_path": path,
                "domain_name": fake.domain_name(),
                "dap_domain_visits_count": fake.random_int(0, 10000),
                "metadata": {
                    "crawl_depth": fake.random_int(1, 8),
                    "creator": "load_test_documents",
                    "download_bytes": fake.random_int(1024, 15728640),
                    "download_milliseconds": fake.random_int(0, 30000),
                    "source_url": fake.url(),
                },
            }
            documents.append(doc)

        current_date += timedelta(days=1)

    return documents


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Load Test Documents Script")
    subparsers = parser.add_subparsers(dest="target", help="Target index for test documents")

    parser_search = subparsers.add_parser("search", help="search help")
    parser_search.add_argument(
        "--from_date", type=str, required=True, help="Start date for fake docs, in YYYY-MM-DD format"
    )
    parser_search.add_argument(
        "--to_date", type=str, required=True, help="End date for fake docs, in YYYY-MM-DD format"
    )
    parser_search.add_argument("--docs_per_day", type=int, required=True, help="Number of fake docs to load per day.")

    parser_freshness = subparsers.add_parser("freshness")
    parser_freshness.add_argument(
        "--search_docs", type=int, required=True, help="The number of search docs to create fake freshness docs for"
    )

    args = parser.parse_args()

    searchgov_settings = SearchgovSettings()
    opensearch = SearchGovOpensearch(searchgov_settings=searchgov_settings)
    print(f"Starting load of fake {args.target} docs!")

    if args.target == "search":
        target_index = searchgov_settings.opensearch_search_index
        index_check(target_index, opensearch=opensearch)
        fake_documents = generate_fake_documents(
            from_date=args.from_date, to_date=args.to_date, docs_per_day=args.docs_per_day
        )
    else:
        target_index = searchgov_settings.opensearch_freshness_index
        index_check(target_index, searchgov_settings.opensearch_search_index, opensearch=opensearch)
        fake_documents = generate_fake_freshness_documents(opensearch=opensearch, search_docs=args.search_docs)

    if not opensearch.index_exists(index_name=target_index):
        print(f"Target index {target_index} does not exist")

    batch = [("index", target_index, doc) for doc in fake_documents]
    actions_taken, actions_failed = opensearch.bulk_batch_upload(batch=batch)
    print(f"Loaded {len(actions_taken)} fake docs to opensearch! Encountered {len(actions_failed)} errors!")
