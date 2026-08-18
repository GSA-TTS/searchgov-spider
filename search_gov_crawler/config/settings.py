from pathlib import Path

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchgovSettings(BaseSettings):
    """Global Settings Class That reads from environment or .env file"""

    scrapy_log_level: str = "INFO"
    opensearch_search_host: str = "http://localhost:9200"
    opensearch_search_user: str = ""
    opensearch_search_pass: str = ""
    opensearch_search_index: str = "spider-searchgov"
    opensearch_freshness_index: str = "spider-freshness"
    dap_extractor_schedule: str = ""
    dap_visits_days_back: PositiveInt = 7
    dap_visits_max_age: PositiveInt = 28
    dlm_schedule: str = "30 6 * * *"
    dlm_max_docs: int = 5000

    model_config = SettingsConfigDict(
        dotenv_filtering="only_existing",
        env_file=(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
    )
