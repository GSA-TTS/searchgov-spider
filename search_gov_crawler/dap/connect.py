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


def get_dap_page_by_date(query_date: str, query_limit: int, query_page: int) -> list[dict]:
    """
    Fetches one page of DAP data for a given date.
    """
    dap_api_base_url, dap_api_key = get_dap_api_configs()

    url = (
        f"{dap_api_base_url}/reports/site/data?"
        f"after={query_date}&before={query_date}&"
        f"limit={query_limit}&page={query_page}"
    )

    response = requests.get(url, headers={"x-api-key": dap_api_key, "Accept": "application/json"}, timeout=30)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        log.exception("Error during DAP request: %s", response.text)
        raise

    return response.json()
