import logging
import os
from collections.abc import Generator

import click

from elasticsearch import NotFoundError
from elasticsearch.helpers import scan
from opensearchpy.exceptions import RequestError
from opensearchpy.helpers import streaming_bulk
from pythonjsonlogger.json import JsonFormatter

from search_gov_crawler.search_engines.es_batch_upload import SearchGovElasticsearch
from search_gov_crawler.search_engines.opensearch_batch_upload import SearchGovOpensearch
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("transfer_docs")


def count_matching_documents(es: SearchGovElasticsearch, query: dict) -> int:
    """
    Return count of given query in elasticsearch index
    """
    response = es.client.count(index=es.index_name, body=query)
    return response["count"]


def get_matching_documents(es: SearchGovElasticsearch, query: dict, scroll: str) -> Generator[dict, None, None]:
    """
    Yield documents matching given query from elasticsearch index
    """
    yield from scan(es.client, index=es.index_name, query=query, scroll=scroll)


def create_opensearch_action(document: dict, target_index: str) -> dict:
    """
    Create action dict in format needed for opensearch bulk upload
    """
    source = document["_source"]
    return {"_index": target_index, "_id": source["id"], "_source": source}


def transform_es_template(elasticseach_template: dict) -> dict:
    """
    Gets template from ES and modifies it so it can be applied in opensearch
    """
    index_patterns = elasticseach_template["index_patterns"]
    settings = elasticseach_template["settings"]
    mappings = elasticseach_template["mappings"]

    return {"index_patterns": index_patterns, "template": {"settings": settings, "mappings": mappings}}


def create_opensearch_target(sg_elastic: SearchGovElasticsearch, sg_opensearch: SearchGovOpensearch) -> None:
    """Create opensearch target index and template"""

    template_name = "documents"

    try:
        response = sg_elastic.client.indices.get_template(name=template_name)
    except NotFoundError:
        log.exception("%s template not found in Elasticsearch!", template_name)
        raise

    es_template = response.body.get(template_name)
    os_template = transform_es_template(es_template)
    sg_opensearch.client.indices.put_index_template(name=template_name, body=os_template)

    try:
        sg_opensearch.client.indices.create(index=sg_opensearch.index_name)
    except RequestError:
        log.exception("Index %s already exists, cannot create! Remove create-index flag!", sg_opensearch.index_name)
        raise


def generate_docs_from_elasticsearch(
    sg_elastic: SearchGovElasticsearch,
    target_index: str,
    scroll: str,
) -> Generator[dict]:
    """
    Get all documents from elasticsearch index.  This is a generator that yields one document at a time.
    """
    query = {"query": {"match_all": {}}}
    expected_count = count_matching_documents(sg_elastic, query=query)

    if not expected_count:
        log.error("No documents found! Check query and try again!")
        return

    log.info("Found %s documents to transfer. Starting processing...", expected_count)

    for elasticsearch_doc in get_matching_documents(sg_elastic, query=query, scroll=scroll):
        doc_id = elasticsearch_doc.get("_id", "unknown")
        try:
            opensearch_action = create_opensearch_action(elasticsearch_doc, target_index)
        except Exception:
            log.exception("Error processing document %s", doc_id)
            continue

        yield opensearch_action


def validate_args(source: str | None, target: str | None) -> tuple[str, str]:
    """
    Validate input args and assign defaults
    """
    if not source:
        source = os.getenv("ELASTICSEARCH_SEARCHGOV_INDEX", "development-i14y-documents-searchgov-legacy")
    if not target:
        target = source

    return source, target


@click.group()
def cli(): ...


@cli.command()
@click.argument("source", type=str, default=None)
@click.argument("target", type=str, default=None)
@click.option(
    "--create-target",
    "-ct",
    is_flag=True,
    default=False,
    required=True,
    help="Create target index based on source index.",
)
@click.option("--scroll", type=str, default="60m", help="Length elasticsearch keeps scroll window open.")
def copy_index(source: str, target: str | None, create_target, scroll):
    """
    Transfer docs from i14y index in elasticsearch to opensearch
    """
    source, target = validate_args(source, target)
    sg_es = SearchGovElasticsearch(es_index=source)
    sg_os = SearchGovOpensearch(opensearch_index=target)

    try:
        sg_es.client.indices.exists(index=source)
    except Exception:
        log.exception("Source index %s does not exist in Elasticsearch!", source)
        raise

    if create_target:
        log.info("Creating target template and index...")
        create_opensearch_target(sg_es, sg_os)

    if not sg_os.client.indices.exists(index=sg_os.index_name):
        log.error("Index %s does not exist in Opensearch!", sg_os.index_name)
        raise

    results = {"succeeded": [], "failed": []}
    chunk_size = 100
    for actions, (success, item) in enumerate(
        streaming_bulk(
            sg_os.client,
            actions=generate_docs_from_elasticsearch(sg_es, sg_os.index_name, scroll),
            chunk_size=chunk_size,
        ),
    ):
        if success:
            results["succeeded"].append(item)
        else:
            results["failed"].append(item)
            log.error("Error loading batch of documents into Opensearch!")

        if (actions + 1) % chunk_size == 0 and actions > 0:
            log.error("Ingested documents into Opensearch! Total Ingested: %s", len(results["succeeded"]))

    log.info("Finished loading documents!")
    log.info("Bulk-inserted %s documents to Opensearch index %s.", len(results["succeeded"]), sg_os.index_name)
    if results["failed"]:
        log.info("There were %s errors:", len(results["failed"]))
        for item in results["failed"]:
            log.error(item["index"]["error"])


if __name__ == "__main__":
    cli()
