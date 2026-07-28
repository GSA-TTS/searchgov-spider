from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchgovSettings(BaseSettings):
    """Global Settings Class That reads from environment or .env file"""

    scrapy_log_level: str = "INFO"
    opensearch_search_host: str = "http://localhost:9200"
    opensearch_search_user: str = ""
    opensearch_search_password: str = ""
    opensearch_search_index: str = "development-i14y-documents-searchgov"
    opensearch_freshness_index: str = "spider-freshness"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        dotenv_filtering="only_existing",
        env_file=(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
    )
