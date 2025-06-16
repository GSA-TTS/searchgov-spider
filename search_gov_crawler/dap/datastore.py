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

    dap_records_aged_off = 0
    age_off_date = datetime.now(UTC) - timedelta(days=days_back)
    min_score = int(age_off_date.strftime("%Y%m%d"))
    keys = redis.keys("dap_visits:*")

    log.info("Checking %d keys for records oder than %s", len(keys), age_off_date.strftime("%Y-%m-%d"))
    for key in keys:
        dap_records_aged_off += redis.zremrangebyscore(name=key, min="-inf", max=min_score)

    return dap_records_aged_off


def get_avg_daily_visits_by_domain(redis: Redis, domain: str, days_back: int) -> dict:
    """
    Get the average daily visits for a domain and all its sub-domains over the last `days_back` days.
    """
    key_prefix = "dap_visits:"

    domain_avg_daily_visits = {}
    min_score = int((datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y%m%d"))
    max_score = int(datetime.now(UTC).strftime("%Y%m%d"))

    domain_keys = list(redis.keys(f"{key_prefix}:*.{domain}"))
    domain_keys.extend(redis.keys(f"{key_prefix}:{domain}"))

    for domain_key in domain_keys:
        visits = redis.zrangebyscore(name=domain_key, min=min_score, max=max_score)
        avg_daily_visits = sum(int(visit) for visit in visits) / days_back if visits else 0
        domain_name = str(domain_key).removeprefix(key_prefix)

        log.info(
            "Average daily visits for domain %s over the last %d days: %.2f",
            domain_name,
            days_back,
            avg_daily_visits,
        )
        domain_avg_daily_visits[domain_name] = avg_daily_visits

    return domain_avg_daily_visits
