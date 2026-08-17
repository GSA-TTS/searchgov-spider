import argparse
import logging
import math
from itertools import batched

from apscheduler.triggers.cron import CronTrigger

from search_gov_crawler.config.settings import SearchgovSettings
from search_gov_crawler.indexing.opensearch import SearchGovOpensearch
from search_gov_crawler.run.schedule import init_singleton_job_scheduler
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT, JsonFormatter
from search_gov_crawler.search_gov_spiders.helpers.freshness_spider import (
    count_matching_documents,
    get_matching_documents,
)

searchgov_settings = SearchgovSettings()

logging.basicConfig(level=searchgov_settings.scrapy_log_level)
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("search_gov_crawler.document_lifecycle_manager")


def process_deletion_batch(opensearch: SearchGovOpensearch, actions: list, urls: dict):
    """Create actions, submit to opensearch, and log results"""

    batch_deletions, batch_failures = opensearch.bulk_batch_upload(batch=actions)
    for deletion in batch_deletions:
        index = deletion["delete"].get("_index")
        doc_id = deletion["delete"].get("_id")
        url = urls.get(doc_id, "missing")
        log.info("Successfully deleted document! index: %s, _id: %s, url: %s", index, doc_id, url)

    for failure in batch_failures:
        index = failure["delete"].get("_index")
        doc_id = failure["delete"].get("_id")
        result = failure["delete"].get("result")
        error_type = failure["delete"].get("error", {}).get("type")
        log.error("Error deleting document! index: %s, _id: %s, error: %s", index, doc_id, error_type or result)

    return batch_deletions, batch_failures


def run_stale_document_deletion(searchgov_settings: SearchgovSettings):
    """
    This function finds all docs in the freshness opensearch index that meet criteria for deletion,
    processing them in batches, first deleting them from the main spider opensearch index and then
    from the freshness index itself.
    """
    opensearch = SearchGovOpensearch(searchgov_settings=searchgov_settings)
    query = {"query": {"term": {"marked_for_deletion": True}}, "sort": [{"checked_at": {"order": "asc"}}]}
    matching_document_count = count_matching_documents(
        opensearch=opensearch, query=query, index_name=searchgov_settings.opensearch_freshness_index
    )

    if not matching_document_count:
        log.info("No documents found as marked for deletion! Stopping process.")
    else:
        log.info("Found %d documents marked for deletion!", matching_document_count)

    matching_docs = get_matching_documents(
        opensearch=opensearch, query=query, scroll="10m", index_name=searchgov_settings.opensearch_freshness_index
    )

    max_batches = math.floor(searchgov_settings.dlm_max_docs / opensearch.batch_size)
    total_deletions = 0
    total_errors = 0
    for idx, docs in enumerate(batched(matching_docs, opensearch.batch_size), start=1):
        if idx > max_batches:
            log.warning(
                "Circuit breaker triggered! Stopping process because next batch would exceed %d documents.",
                searchgov_settings.dlm_max_docs,
            )
            break

        document_urls = {doc["_id"]: doc["_source"]["path"] for doc in docs}
        search_actions = [("delete", searchgov_settings.opensearch_search_index, doc) for doc in docs]
        search_deletions, search_errors = process_deletion_batch(
            opensearch=opensearch, actions=search_actions, urls=document_urls
        )

        freshness_actions = [
            ("delete", searchgov_settings.opensearch_freshness_index, search_deletion_taken["delete"])
            for search_deletion_taken in search_deletions
        ]
        freshness_deletions, freshness_errors = process_deletion_batch(
            opensearch=opensearch, actions=freshness_actions, urls=document_urls
        )
        total_deletions += len(freshness_deletions)
        total_errors += len(search_errors) + len(freshness_errors)

    log.info(
        "Completed Stale Document Deletion! Docs Deleted: %d Errors Encountered: %d", total_deletions, total_errors
    )


def main(searchgov_settings: SearchgovSettings) -> None:
    """Main function, handles getting the schedule and starting the scheduler for document lifecycle management"""

    try:
        cron_trigger = CronTrigger.from_crontab(expr=searchgov_settings.dlm_schedule)
    except (AttributeError, TypeError, ValueError):
        log.exception("Invalid crontab expression from DLM_SCHEDULE: %s", searchgov_settings.dlm_schedule)
        raise

    scheduler = init_singleton_job_scheduler()
    scheduler.add_job(func=run_stale_document_deletion, trigger=cron_trigger, name="document_lifecycle_manager")

    log.info(
        "Starting scheduler for document lifecycle manager based on crontab expression %s",
        searchgov_settings.dlm_schedule,
    )

    scheduler.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Document Lifecycle Manager job")
    parser.add_argument(
        "--run-now", action="store_true", default=False, help="Flag to trigger a single run, right now (default False)"
    )

    args = parser.parse_args()
    if not args.run_now:
        main(searchgov_settings=searchgov_settings)
    else:
        run_stale_document_deletion(searchgov_settings=searchgov_settings)
