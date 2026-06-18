import ast
from collections.abc import Generator

from opensearchpy.helpers import scan

from search_gov_crawler.indexing.opensearch import SearchGovOpensearch


def ensure_valid_query(opensearch: SearchGovOpensearch, query: str) -> dict:
    """Check input query to ensure validity"""
    formatted_query = ast.literal_eval(query)
    if not isinstance(formatted_query, dict):
        msg = "Query input is not a valid dictionary!"
        raise TypeError(msg)

    response = opensearch.client.indices.validate_query(index=opensearch.index_name, body=formatted_query, explain=True)
    if str(response["valid"]).lower() == "false":
        msg = f"Invalid query! Error: {response['error']}"
        explanations = response.get("explanations", [])
        for explanation in explanations:
            explanation_msg = explanation.get("explanation", "")
            msg += f" {explanation_msg}"
        raise ValueError(msg)

    return formatted_query


def count_matching_documents(opensearch: SearchGovOpensearch, query: dict) -> int:
    """
    Return count of documents matching given query from opensearch index
    """
    query.pop("size", None)  # ensure size is not set for count query
    return opensearch.client.count(index=opensearch.index_name, body=query)["count"]


def get_matching_documents(opensearch: SearchGovOpensearch, query: dict, scroll: str) -> Generator[dict, None, None]:
    """
    Yield documents matching given query from opensearch index
    """
    yield from scan(opensearch.client, index=opensearch.index_name, query=query, scroll=scroll)
