import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Self

from apscheduler.triggers.cron import CronTrigger

from search_gov_crawler.search_gov_app.database import get_database_connection, select_active_crawl_configs
from search_gov_crawler.search_gov_spiders.helpers.domain_spider import ALLOWED_CONTENT_TYPE_OUTPUT_MAP


class CrawlConfigValidationError(Exception):
    """Custom exception for crawl config validation errors."""


@dataclass
class CrawlConfig:
    """
    Represents a single crawl config record.  All fields required except schedule and depth_limit.
    In normal operations, When schedule is blank, a job will not be scheduled.  When running
    a benchmark, schedule is ignored.
    """

    name: str
    allow_query_string: bool
    allowed_domains: str
    handle_javascript: bool
    starting_urls: str
    output_target: str
    depth_limit: int
    job_id: str | None = field(default=None, init=False)
    deny_paths: list | None = None
    schedule: str | None = None
    sitemap_urls: list | None = None
    check_sitemap_hours: int | None = None

    def __post_init__(self):
        """Populate id field and perform validation"""
        self._validate_required_fields()
        self._validate_types()
        self._validate_fields()
        self.job_id = self.name.lower().replace(" ", "-").replace("---", "-")

    def _validate_types(self) -> None:
        """Check field types against class definition to ensure compatability"""

        for field in fields(self):
            value = getattr(self, field.name)
            if hasattr(field.type, "__args__"):
                # for optional fields
                valid_types = field.type.__args__
                if value is None and type(None) in valid_types:
                    continue

                for valid_type in (vt for vt in valid_types if vt is not type(None)):
                    if not isinstance(value, valid_type):
                        msg = (
                            f"Invalid type! Field {field.name} with value "
                            f"{getattr(self, field.name)} must be one of types {[vt.__name__ for vt in valid_types]}"
                        )
                        raise CrawlConfigValidationError(msg)
            elif not isinstance(value, field.type):
                msg = (
                    f"Invalid type! Field {field.name} with value {getattr(self, field.name)} must be type {field.type}"
                )
                raise CrawlConfigValidationError(msg)

    def _validate_fields(self) -> None:
        """Validate Individual Fields"""

        # validate no duplicates in deny_paths
        if self.deny_paths is not None:
            unique_deny_paths = set(self.deny_paths)
            if len(unique_deny_paths) != len(self.deny_paths):
                msg = f"Values in deny_paths must be unique! {self.name} has duplicates!"
                raise CrawlConfigValidationError(msg)

        # validate output_target values
        if self.output_target not in ALLOWED_CONTENT_TYPE_OUTPUT_MAP:
            msg = (
                f"Invalid output_target value {self.output_target}! "
                f"Must be one of {list(ALLOWED_CONTENT_TYPE_OUTPUT_MAP.keys())}"
            )
            raise CrawlConfigValidationError(msg)

        # validate schedule
        if self.schedule:
            try:
                CronTrigger.from_crontab(self.schedule)
            except ValueError as err:
                msg = f"Invalid cron expression in schedule value: {self.schedule}"
                raise CrawlConfigValidationError(msg) from err

    def _validate_required_fields(self) -> None:
        """Ensure all required fields are present"""

        missing_field_names = []
        for field in fields(self):
            if field.name in {"schedule", "deny_paths", "sitemap_urls", "check_sitemap_hours", "job_id"}:
                pass
            elif getattr(self, field.name) is None:
                missing_field_names.append(field.name)

        if missing_field_names:
            msg = f"All CrawlConfig fields are required!  Add values for {','.join(missing_field_names)}"
            raise CrawlConfigValidationError(msg)

    def to_dict(self, *, exclude: tuple = ()) -> dict:
        """Helper method to return dataclass as dictionary.  Exclude fields listed in exclude arg."""
        crawl_config = asdict(self)
        for field in exclude:
            crawl_config.pop(field, None)

        return crawl_config


@dataclass
class CrawlConfigs:
    """Represents a list of crawl config records"""

    root: list[CrawlConfig]

    def __iter__(self):
        """Iterate directly from CrawlConfigs instance instead of calling root."""
        yield from self.root

    def __post_init__(self):
        """Perform validations on entire list"""
        unique_job_ids = set()
        unique_domains_by_target = set()
        for site in self:
            job_id = site.job_id
            if job_id in unique_job_ids:
                msg = f"Duplicate job_id found: {job_id} in site:\n{site}"
                raise CrawlConfigValidationError(msg)

            unique_job_ids.add(job_id)

            site_key = f"{site.output_target}::{site.allowed_domains}"
            if site_key in unique_domains_by_target:
                msg = (
                    "The combination of allowed_domain and output_target must be unique in file. "
                    f"Duplicate site domain:\n{site}"
                )
                raise CrawlConfigValidationError(msg)
            unique_domains_by_target.add(site_key)

    @classmethod
    def from_database(cls) -> Self:
        """Create CrawlConfigs instance from the searchgov database"""
        with get_database_connection() as connection:
            records = select_active_crawl_configs(connection)

        for record in records:
            record["allow_query_string"] = bool(record["allow_query_string"])
            record["handle_javascript"] = bool(record["handle_javascript"])
            record["output_target"] = (
                "elasticsearch" if record["output_target"] == "searchengine" else record["output_target"]
            )
            record["deny_paths"] = json.loads(record["deny_paths"]) if record["deny_paths"] else []
            record["sitemap_urls"] = json.loads(record["sitemap_urls"]) if record["sitemap_urls"] else []

            record["starting_urls"] = ",".join(json.loads(record["starting_urls"]) if record["starting_urls"] else [])
            record["allowed_domains"] = ",".join(
                json.loads(record["allowed_domains"]) if record["allowed_domains"] else []
            )

        crawl_configs = [CrawlConfig(**record) for record in records]
        return cls(crawl_configs)

    @classmethod
    def from_file(cls, file: Path) -> Self:
        """Create CrawlConfigs instance from file path to json input file"""

        records = json.loads(file.read_text(encoding="UTF-8"))
        crawl_configs = [CrawlConfig(**record) for record in records]
        return cls(crawl_configs)

    def scheduled(self):
        """Yield only records that have a schedule"""
        yield from (crawl_config for crawl_config in self if crawl_config.schedule)
