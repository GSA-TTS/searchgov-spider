"""
Deletes all records from the spider index in opensearch based on the given domain.
Usage:
    python scripts/delete_by_domain.py <domain_name> [--apply]
"""

import argparse

from opensearchpy import OpenSearch

from search_gov_crawler.config.settings import SearchgovSettings
from search_gov_crawler.indexing.opensearch import SearchGovOpensearch


def initialize_opensearch(searchgov_settings: SearchgovSettings) -> tuple[OpenSearch, str]:
    """Initialize the OpenSearch client."""

    es = SearchGovOpensearch(searchgov_settings=searchgov_settings)
    return es.client, es.index_name


def delete_by_domain(searchgov_settings: SearchgovSettings, domain_name: str, apply: bool) -> None:  # noqa: FBT001
    """Delete documents from Elasticsearch by domain."""

    es_client, index_name = initialize_opensearch(searchgov_settings=searchgov_settings)
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

    settings = SearchgovSettings()
    # Call the function with the provided domain
    delete_by_domain(searchgov_settings=settings, domain_name=args.domain, apply=args.apply)
