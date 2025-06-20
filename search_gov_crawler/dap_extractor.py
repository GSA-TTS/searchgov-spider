import argparse
import logging
import os
from datetime import UTC, datetime, timedelta

from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from redis import Redis

from search_gov_crawler.dap.connect import get_dap_page_by_date
from search_gov_crawler.dap.datastore import age_off_dap_records, write_dap_record_to_redis
from search_gov_crawler.dap.schedule import ensure_positive_int, init_scheduler
from search_gov_crawler.dap.transform import transform_dap_response
from search_gov_crawler.scheduling.redis import get_redis_connection_args
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT, JsonFormatter

load_dotenv()

logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
log = logging.getLogger("search_gov_crawler.dap_extractor")


def run_dap_extractor(days_back: int, max_age: int) -> None:
    """
    Function to run the DAP retrieval job.

    Runs for the last `days_back` days, starting at yesterday, and writes the data to Redis.

    Args:
        days_back (int): Number of days back to retrieve DAP data.
        max_age (int): Maximum number of days of DAP data to keep in Redis.
    """
    log.info("Starting DAP data retrieval job for last %s days", days_back)

    redis_client = Redis(**get_redis_connection_args(db=2))

    for range_day in range(days_back):
        query_date = (datetime.now(UTC) - timedelta(days=range_day + 1)).strftime("%Y-%m-%d")
        log.info("Running DAP job for date: %s", query_date)

        # query 1000 record pages from DAP API until an empty response is seen
        query_limit = 1000
        query_page = 0
        api_has_data = True

        dap_response = []
        while api_has_data:
            query_page += 1
            dap_page = get_dap_page_by_date(query_date, query_limit, query_page)
            log.info("Fetched %s records on page %s for date: %s", len(dap_page), query_page, query_date)

            if dap_page:
                dap_response.extend(dap_page)
            else:
                api_has_data = False
                log.info("No more data found for date: %s", query_date)

        log.info("Fetched %s records fetched from DAP for date: %s", len(dap_response), query_date)

        # transform and normalize dap records into a useful format
        transformed_dap_records = transform_dap_response(dap_response)

        # write all the transformed records to redis
        for transformed_dap_record in transformed_dap_records:
            write_dap_record_to_redis(redis=redis_client, **transformed_dap_record)

        log.info("Wrote %s records to Redis for date: %s", len(transformed_dap_records), query_date)

    # age off records older than a certain number of days
    log.info("Starting Age off of records older than %s days!", max_age)
    dap_records_aged_off = age_off_dap_records(redis=redis_client, days_back=max_age)

    log.info("Aged off %d records older than %d days", dap_records_aged_off, max_age)


def main(days_back: int, max_age: int) -> None:
    """Main function, handles getting the schedule and starting the scheduler for the dap extractor job"""

    dap_extractor_schedule = os.getenv("DAP_EXTRACTOR_SCHEDULE")
    try:
        cron_trigger = CronTrigger.from_crontab(dap_extractor_schedule)
    except (AttributeError, TypeError, ValueError):
        log.exception("Invalid crontab expression from in DAP_EXTRACTOR_SCHEDULE!")
        raise

    scheduler = init_scheduler()
    scheduler.add_job(func=run_dap_extractor, trigger=cron_trigger, args=(days_back, max_age), name="dap_extractor")

    log.info("Starting scheduler for dap extractor based on crontab expression %s", dap_extractor_schedule)

    scheduler.start()


if __name__ == "__main__":
    # Entry point for the script to run the DAP data retrieval job.

    dap_days_back = ensure_positive_int(os.getenv("DAP_VISITS_DAYS_BACK", "7"))
    dap_max_age = ensure_positive_int(os.getenv("DAP_VISITS_MAX_AGE", "28"))

    parser = argparse.ArgumentParser(description="Run DAP data retrieval job")
    parser.add_argument(
        "--days-back",
        nargs="?",
        const=dap_days_back,
        default=dap_days_back,
        type=ensure_positive_int,
        help=f"Number of days back to retrieve DAP data (default {dap_days_back})",
    )
    parser.add_argument(
        "--max-age",
        nargs="?",
        const=dap_max_age,
        default=dap_max_age,
        type=ensure_positive_int,
        help=f"Number of days back to retrieve DAP data (default {dap_max_age})",
    )

    parser.add_argument(
        "--run-now",
        action="store_true",
        default=False,
        help="Flag to trigger a single run, right now (default False)",
    )

    args = parser.parse_args()
    if not args.run_now:
        main(days_back=args.days_back, max_age=args.max_age)
    else:
        run_dap_extractor(days_back=args.days_back, max_age=args.max_age)
