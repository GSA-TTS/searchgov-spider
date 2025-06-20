import logging
from collections import defaultdict

log = logging.getLogger(__name__)

INVALID_DOMAINS = ("(not set)", "(other)")


def domain_is_valid(domain: str) -> bool:
    """
    Checks if the domain is a valid VALIS domain.
    """

    if not domain:
        log.debug("Invalid domain: %s", domain)
        return False

    if domain in INVALID_DOMAINS:
        log.debug("Invalid domain: %s", domain)
        return False

    if domain.replace(".", "").isdigit():
        log.debug("Invalid domain: %s", domain)
        return False

    if domain.startswith(".") or domain.endswith("."):
        log.debug("Invalid domain: %s", domain)
        return False

    if domain.count(".") == 0:
        log.debug("Invalid domain: %s", domain)
        return False

    return True


def transform_dap_response(dap_response: list[dict]) -> list[dict]:
    """Transforms DAP response into the format we need."""

    default_dict = defaultdict(dict)

    for record in dap_response:
        domain = str(record.get("domain", "")).lower().removeprefix("www.")

        if domain_is_valid(domain):
            visits = record.get("visits", 0)
            date = record["date"]
            domain_date_id = f"{domain}-{date}"

            default_dict[domain_date_id].update(
                {
                    "domain": domain,
                    "visits": default_dict[domain_date_id].get("visits", 0) + visits,
                    "date": date,
                },
            )

    return list(default_dict.values())
