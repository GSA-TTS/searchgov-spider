import warnings

import click
from elastic_transport import ObjectApiResponse, SecurityWarning
from elasticsearch import Elasticsearch, ElasticsearchWarning
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from urllib3.exceptions import InsecureRequestWarning

from search_gov_crawler.search_engines.es_batch_upload import SearchGovElasticsearch


def initialize_elasticsearch() -> tuple[Elasticsearch, str]:
    """Initialize the Elasticsearch client."""

    es = SearchGovElasticsearch()
    return es.client, es.index_name


def get_common_query_args(search_terms: str) -> dict:
    """Return common query args"""
    return {
        "query": {
            "function_score": {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "bool": {
                                    "should": [
                                        {"match": {"bigrams": {"operator": "and", "query": search_terms}}},
                                        {"term": {"promote": True}},
                                    ],
                                    "must": [
                                        {
                                            "bool": {
                                                "should": [
                                                    {
                                                        "bool": {
                                                            "must": [
                                                                {
                                                                    "simple_query_string": {
                                                                        "query": search_terms,
                                                                        "fields": [
                                                                            "title_en^2",
                                                                            "description_en^1.5",
                                                                            "content_en",
                                                                        ],
                                                                    }
                                                                },
                                                                {
                                                                    "bool": {
                                                                        "should": [
                                                                            {
                                                                                "common": {
                                                                                    "title_en": {
                                                                                        "query": search_terms,
                                                                                        "cutoff_frequency": 0.05,
                                                                                        "minimum_should_match": {
                                                                                            "low_freq": "3\u003c90%",
                                                                                            "high_freq": "2\u003c90%",
                                                                                        },
                                                                                    },
                                                                                },
                                                                            },
                                                                            {
                                                                                "common": {
                                                                                    "description_en": {
                                                                                        "query": search_terms,
                                                                                        "cutoff_frequency": 0.05,
                                                                                        "minimum_should_match": {
                                                                                            "low_freq": "3\u003c90%",
                                                                                            "high_freq": "2\u003c90%",
                                                                                        },
                                                                                    },
                                                                                },
                                                                            },
                                                                            {
                                                                                "common": {
                                                                                    "content_en": {
                                                                                        "query": search_terms,
                                                                                        "cutoff_frequency": 0.05,
                                                                                        "minimum_should_match": {
                                                                                            "low_freq": "3\u003c90%",
                                                                                            "high_freq": "2\u003c90%",
                                                                                        },
                                                                                    },
                                                                                },
                                                                            },
                                                                        ],
                                                                    },
                                                                },
                                                            ],
                                                        },
                                                    },
                                                    {"match": {"audience": {"operator": "and", "query": search_terms}}},
                                                    {"match": {"basename": {"operator": "and", "query": search_terms}}},
                                                    {
                                                        "match": {
                                                            "searchgov_custom1": {
                                                                "operator": "and",
                                                                "query": search_terms,
                                                            },
                                                        },
                                                    },
                                                    {
                                                        "match": {
                                                            "searchgov_custom2": {
                                                                "operator": "and",
                                                                "query": search_terms,
                                                            },
                                                        },
                                                    },
                                                    {
                                                        "match": {
                                                            "searchgov_custom3": {
                                                                "operator": "and",
                                                                "query": search_terms,
                                                            },
                                                        },
                                                    },
                                                    {"match": {"tags": {"operator": "and", "query": search_terms}}},
                                                ],
                                            },
                                        },
                                    ],
                                },
                            },
                        ],
                        "filter": [
                            {
                                "bool": {
                                    "must": [{"term": {"language": "en"}}],
                                    "minimum_should_match": "100%",
                                    "should": [
                                        {
                                            "bool": {
                                                "minimum_should_match": 1,
                                                # This is what is changed for an affiliate search
                                                "should": [{"bool": {"must": [{"match_all": {}}]}}],
                                            },
                                        },
                                    ],
                                },
                            },
                        ],
                    },
                },
                "functions": [
                    {"gauss": {"changed": {"origin": "now", "scale": "1825d", "offset": "30d", "decay": 0.3}}},
                    {
                        "filter": {"terms": {"extension": ["doc", "docx", "pdf", "ppt", "pptx", "xls", "xlsx"]}},
                        "weight": ".75",
                    },
                    {"field_value_factor": {"field": "click_count", "modifier": "log1p", "factor": 2, "missing": 1}},
                    # this is the new scoring function, this is what you might have to tweak
                    {
                        "field_value_factor": {
                            "field": "dap_domain_visits_count",
                            "modifier": "log1p",
                            "factor": 2,
                            "missing": 1,
                        },
                    },
                ],
            },
        },
        "aggregations": {
            "audience": {"terms": {"field": "audience"}},
            "content_type": {"terms": {"field": "content_type"}},
            "mime_type": {"terms": {"field": "mime_type"}},
            "searchgov_custom1": {"terms": {"field": "searchgov_custom1"}},
            "searchgov_custom2": {"terms": {"field": "searchgov_custom2"}},
            "searchgov_custom3": {"terms": {"field": "searchgov_custom3"}},
            "tags": {"terms": {"field": "tags"}},
            "created": {
                "date_range": {
                    "field": "created",
                    "format": "8M/d/u",
                    "ranges": [
                        {"key": "Last Week", "from": "now-1w", "to": "now"},
                        {"key": "Last Month", "from": "now-1M", "to": "now"},
                        {"key": "Last Year", "from": "now-12M", "to": "now"},
                    ],
                },
            },
            "changed": {
                "date_range": {
                    "field": "changed",
                    "format": "8M/d/u",
                    "ranges": [
                        {"key": "Last Week", "from": "now-1w", "to": "now"},
                        {"key": "Last Month", "from": "now-1M", "to": "now"},
                        {"key": "Last Year", "from": "now-12M", "to": "now"},
                    ],
                },
            },
        },
        "suggest": {
            "suggestion": {
                "text": search_terms,
                "phrase": {
                    "field": "bigrams",
                    "size": 1,
                    "highlight": {"pre_tag": "", "post_tag": ""},
                    "collate": {
                        "query": {
                            "source": {"multi_match": {"query": "{{suggestion}}", "type": "phrase", "fields": "*_en"}}
                        },
                    },
                },
            },
        },
        "highlight": {
            "pre_tags": [""],
            "post_tags": [""],
            "fields": {
                "title_en": {"number_of_fragments": 0, "type": "fvh"},
                "description_en": {"fragment_size": 75, "number_of_fragments": 2, "type": "fvh"},
                "content_en": {"fragment_size": 75, "number_of_fragments": 2, "type": "fvh"},
            },
        },
        "source": [
            "title_en",
            "path",
            "created",
            "changed",
            "thumbnail_url",
            "language",
            "domain_name",
            "url_path",
        ],
    }


def print_results(response: ObjectApiResponse, search_terms: str, index_name: str, page: int) -> None:
    """Common function to print results from queries"""

    total = response.body["hits"]["total"]["value"]
    max_score = response.body["hits"]["max_score"]
    hits = response.body["hits"]["hits"]

    title = f"Search Results: {search_terms}"
    subtitle = f"Index: {index_name:<20} Total Hits: {total:<5} Max Score: {max_score:<15} Page: {page}"
    parts = []

    if hits:
        for hit in hits:
            text = Text()
            highlights = hit["highlight"].get("content_en", [])
            highlights.extend(hit["highlight"].get("description_en", []))
            description = " ... ".join(highlights)

            text.append(hit["_source"].get("title_en"), style="bold cyan")
            text.append("\n")
            text.append(description)
            text.append("\n")
            path = hit["_source"].get("path")
            text.append(path, style=f"link {path}")
            text.append("\n\n")
            parts.append(text)
    else:
        parts.append("No Data!")

    console = Console()
    console.print(Panel(Text.assemble(*parts), title=title, subtitle=subtitle), highlight=True)


def add_domains_to_query(common_query_args: dict, domains: str) -> dict:
    """Update domains filter with one or more domains passed in from cli"""

    multi_domain_should = [
        {"bool": {"must": [{"term": {"domain_name": {"value": domain_name}}}]}} for domain_name in domains.split(",")
    ]

    new_query_filters = [
        {
            "bool": {
                "must": [{"term": {"language": "en"}}],
                "minimum_should_match": "100%",
                "should": [
                    {
                        "bool": {
                            "minimum_should_match": 1,
                            "should": multi_domain_should,
                        },
                    },
                ],
            },
        },
    ]

    common_query_args["query"]["function_score"]["query"]["bool"]["filter"] = new_query_filters
    return common_query_args


@click.group()
def cli(): ...


@cli.command()
@click.argument("search_term", nargs=-1, required=True)
@click.option("--size", type=int, default=10, help="Size of results page")
@click.option("--page", type=int, default=1, help="Page of results to display")
def full_govt_search(search_term: str, size: int, page: int) -> None:
    """Mimic search.gov results page with full governtment search.  Used for testing query relevance"""

    es_client, index_name = initialize_elasticsearch()

    search_terms = " ".join(search_term)

    page_from = (page - 1) * size
    custom_query_args = {"index": index_name, "from": page_from, "size": size}
    query_args = custom_query_args | get_common_query_args(search_terms)
    response = es_client.search(**query_args)

    print_results(response=response, search_terms=search_terms, index_name=index_name, page=page)


@cli.command()
@click.argument("search_term", nargs=-1, required=True)
@click.option("--domains", type=str, required=True, help="Comma separated list of domains to search")
@click.option("--size", type=int, default=10, help="Size of results page")
@click.option("--page", type=int, default=1, help="Page of results to display")
def affiliate_search(search_term: str, domains: str, size: int, page: int) -> None:
    """Mimic search.gov results page with affiliate search.  Used for testing query relevance"""

    es_client, index_name = initialize_elasticsearch()

    search_terms = " ".join(search_term)

    page_from = (page - 1) * size
    custom_query_args = {"index": index_name, "from": page_from, "size": size}
    common_query_args = get_common_query_args(search_terms)
    affiliate_query_args = add_domains_to_query(common_query_args=common_query_args, domains=domains)

    query_args = custom_query_args | affiliate_query_args
    response = es_client.search(**query_args)

    print_results(response=response, search_terms=search_terms, index_name=index_name, page=page)


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=ElasticsearchWarning)
    warnings.filterwarnings("ignore", category=InsecureRequestWarning)
    warnings.filterwarnings("ignore", category=SecurityWarning)
    cli()
