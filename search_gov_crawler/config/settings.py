import logging
from pathlib import Path

from pydantic import PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

MAX_OPENSEARCH_QUERY_DOCS = 10000


class SearchgovSettings(BaseSettings):
    """Global Settings Class That reads from environment or .env file"""

    scrapy_log_level: str = "INFO"
    opensearch_search_host: str = "http://localhost:9200"
    opensearch_search_user: str = ""
    opensearch_search_password: str = ""
    opensearch_search_index: str = "spider-searchgov"
    opensearch_freshness_index: str = "spider-freshness"
    dap_extractor_schedule: str = ""
    dap_visits_days_back: PositiveInt = 7
    dap_visits_max_age: PositiveInt = 28
    dlm_schedule: str = "45 * * * *"
    dlm_max_docs: PositiveInt = 500

    model_config = SettingsConfigDict(
        dotenv_filtering="only_existing",
        env_file=(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
    )

    @field_validator("dlm_max_docs", mode="after")
    @classmethod
    def cap_max_docs(cls, v: int) -> int:
        """
        Validator to ensure dlm_max_docs is not larger than 10000 because that is the maximum
        number of documents allowed in a standard opensearch search query.
        """
        if v > MAX_OPENSEARCH_QUERY_DOCS:
            log.warning("Setting dlm_max_docs reduced from %d to %d", v, MAX_OPENSEARCH_QUERY_DOCS)
            return MAX_OPENSEARCH_QUERY_DOCS

        return v
