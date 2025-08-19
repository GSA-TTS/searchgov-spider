import logging
import os

import requests

log = logging.getLogger(__name__)


def get_dap_api_configs() -> tuple:
    """Retrieves DAP API base URL and API key from environment variables."""

    try:
        dap_api_base_url = os.environ["DAP_API_BASE_URL"]
    except KeyError as err:
        msg = "Missing environment variable value for DAP_API_BASE_URL"
        raise ValueError(msg) from err

    try:
        data_gov_api_key = os.environ["DATA_GOV_API_KEY"]
    except KeyError as err:
        msg = "Missing environment variable value for DATA_GOV_API_KEY"
        raise ValueError(msg) from err

    return dap_api_base_url, data_gov_api_key


def get_dap_data_by_date(session: requests.Session, dap_endpoint: str, query_date: str) -> list:
    """Make requests paging through DAP API response to get all data for a given date."""

    dap_response = []
    query_page = 0
    api_has_data = True

    data_endpoint = f"{dap_endpoint}/reports/site/data"

    while api_has_data:
        query_page += 1

        params = {
            "after": query_date,
            "before": query_date,
            "limit": 1000,
            "page": query_page,
        }

        response = session.get(data_endpoint, params=params, timeout=30)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            log.exception(
                "Error during DAP request: status_code=%s, reason=%s, url=%s",
                response.status_code,
                response.reason,
                response.url,
            )
            raise

        dap_page = response.json()

        if dap_page:
            log.info("Fetched %s records on page %s for date: %s", len(dap_page), query_page, query_date)
            dap_response.extend(dap_page)
        else:
            log.info("No more data found for date: %s", query_date)
            api_has_data = False

    return dap_response
