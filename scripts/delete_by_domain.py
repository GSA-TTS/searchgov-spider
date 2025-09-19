"""
Deletes all records from the spider index in elasticsearch based on the given domain.
Usage:
    python scripts/delete_by_domain.py <domain_name> [--apply]
"""

import argparse

from elasticsearch import Elasticsearch

from search_gov_crawler.search_engines.es_batch_upload import SearchGovElasticsearch


def initialize_elasticsearch() -> tuple[Elasticsearch, str]:
    """Initialize the Elasticsearch client."""

    es = SearchGovElasticsearch()
    return es.client, es.index_name


def delete_by_domain(domain_name: str, apply: bool) -> None:
    """Delete documents from Elasticsearch by domain."""

    es_client, index_name = initialize_elasticsearch()
    query = {"query": {"term": {"domain_name": {"value": domain_name}}}}

    response = es_client.count(index=index_name, body=query)
    print(response)

    if response["count"] > 0:
        if apply:
            print(f"Deleting {response['count']} documents from index {index_name} for domain {domain_name}")
            response = es_client.delete_by_query(index=index_name, body=query)
            print(response)
            print(f"Deleted {response['deleted']} documents from index {index_name} for domain {domain_name}")
        else:
            print(f"Found {response['count']} documents in index {index_name} for domain {domain_name}")
            print("Use --apply to delete these documents.")

    else:
        print(f"No documents found for domain {domain_name} in index {index_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete documents from Elasticsearch by domain.")
    parser.add_argument("domain", type=str, help="Domain name to delete documents for.")
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Apply the deletion. Without this flag, it will only count the documents.",
    )
    args = parser.parse_args()

    # Call the function with the provided domain
    delete_by_domain(args.domain, args.apply)
