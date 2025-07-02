import logging
from datetime import UTC, datetime, timedelta

from redis import Redis

log = logging.getLogger(__name__)


def write_dap_record_to_redis(redis: Redis, domain: str, date: str, visits: int) -> None:
    """
    Writes a DAP record to Redis.
    """

    key = f"dap_visits:{domain}"
    name = str(visits)
    score = int(date.replace("-", ""))

    redis.zadd(key, {name: score})


def age_off_dap_records(redis: Redis, days_back: int) -> int:
    """
    Removes DAP records older than `days_back` days.
    """

    age_off_date = datetime.now(UTC) - timedelta(days=days_back)
    min_score = int(age_off_date.strftime("%Y%m%d"))

    log.info("Checking keys for records older than %s", age_off_date.strftime("%Y-%m-%d"))
    pipe = redis.pipeline()
    for key in redis.scan_iter(match="dap_visits:*"):
        pipe.zremrangebyscore(name=key, min="-inf", max=min_score)

    results = pipe.execute()
    return sum(results)


def get_avg_daily_visits_by_domain(redis: Redis, domain: str, days_back: int) -> dict:
    """
    Get the average daily visits for a domain and all its sub-domains over the last `days_back` days.
    """
    key_prefix = "dap_visits:"

    # Use yesterday as basis for these calculations to lessen the impact of DAP data not being available
    base_datetime = datetime.now(UTC) - timedelta(days=1)
    min_score = int((base_datetime - timedelta(days=days_back)).strftime("%Y%m%d"))
    max_score = int(base_datetime.strftime("%Y%m%d"))

    domain_keys = [bytes(key).decode("utf-8") for key in redis.scan_iter(f"{key_prefix}*.{domain}")]
    domain_keys.extend([bytes(key).decode("utf-8") for key in redis.scan_iter(f"{key_prefix}{domain}")])
    pipe = redis.pipeline()

    for domain_key in domain_keys:
        pipe.zrangebyscore(name=domain_key, min=min_score, max=max_score)

    results = pipe.execute()

    try:
        domain_key_visits = list(zip(domain_keys, results, strict=True))
    except ValueError:
        msg = "Cannot get avg daily visits.  Invalid response from redis pipeline.  Expceted: %d, Got: %d"
        log.exception(msg, len(domain_keys), len(results))
        return {}

    domain_avg_daily_visits = {}
    for domain_key, visits in domain_key_visits:
        avg_daily_visits = sum(int(visit) for visit in visits) / days_back if visits else 0
        domain_name = str(domain_key).removeprefix(key_prefix)
        log.debug(
            "Average daily visits for domain %s over the last %d days: %.0f",
            domain_name,
            days_back,
            avg_daily_visits,
        )
        domain_avg_daily_visits[domain_name] = round(avg_daily_visits)

    return domain_avg_daily_visits
