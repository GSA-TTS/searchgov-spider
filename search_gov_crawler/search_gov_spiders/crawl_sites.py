import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Self

from apscheduler.triggers.cron import CronTrigger

from search_gov_crawler.search_gov_spiders.helpers.domain_spider import ALLOWED_CONTENT_TYPE_OUTPUT_MAP


@dataclass
class CrawlSite:
    """
    Represents a single crawl site record.  All fields required except schedule and depth_limit.
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
    deny_paths: list | None = None
    schedule: str | None = None
    sitemap_url: str | None = None
    check_sitemap_hours: int | None = None

    def __post_init__(self):
        """Perform validation on record"""
        self._validate_required_fields()
        self._validate_types()
        self._validate_fields()

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
                        raise TypeError(msg)
            elif not isinstance(value, field.type):
                msg = (
                    f"Invalid type! Field {field.name} with value {getattr(self, field.name)} must be type {field.type}"
                )
                raise TypeError(msg)

    def _validate_fields(self) -> None:
        """Validate Individual Fields"""

        # validate no duplicates in deny_paths
        if self.deny_paths is not None:
            unique_deny_paths = set(self.deny_paths)
            if len(unique_deny_paths) != len(self.deny_paths):
                msg = f"Values in deny_paths must be unique! {self.name} has duplicates!"
                raise TypeError(msg)

        # validate output_target values
        if self.output_target not in ALLOWED_CONTENT_TYPE_OUTPUT_MAP:
            msg = (
                f"Invalid output_target value {self.output_target}! "
                f"Must be one of {list(ALLOWED_CONTENT_TYPE_OUTPUT_MAP.keys())}"
            )
            raise TypeError(msg)

        # validate schedule
        if self.schedule:
            try:
                CronTrigger.from_crontab(self.schedule)
            except ValueError as err:
                msg = f"Invalid cron expression in schedule value: {self.schedule}"
                raise ValueError(msg) from err

    def _validate_required_fields(self) -> None:
        """Ensure all required fields are present"""

        missing_field_names = []
        for field in fields(self):
            if field.name in {"schedule", "deny_paths", "sitemap_url", "check_sitemap_hours"}:
                pass
            elif getattr(self, field.name) is None:
                missing_field_names.append(field.name)

        if missing_field_names:
            msg = f"All CrawlSite fields are required!  Add values for {','.join(missing_field_names)}"
            raise TypeError(msg)

    def to_dict(self, *, exclude: tuple = ()) -> dict:
        """Helper method to return dataclass as dictionary.  Exclude fields listed in exclude arg."""
        crawl_site = asdict(self)
        for field in exclude:
            crawl_site.pop(field, None)

        return crawl_site


@dataclass
class CrawlSites:
    """Represents a single crawl site record"""

    root: list[CrawlSite]

    def __iter__(self):
        """Iterate directly from CrawlSites instance instead of calling root."""
        yield from self.root

    def __post_init__(self):
        """Perform validations on entire list"""
        domains_map = {}
        for site in self.root:
            site_key = f"{site.output_target}::{site.allowed_domains}"
            if site_key in domains_map:
                msg = (
                    "The combination of allowed_domain and starting_urls must be unique in file. "
                    f"Duplicate site domain:\n{site}"
                )
                raise TypeError(msg)
            domains_map[site_key] = True

    @classmethod
    def from_file(cls, file: Path) -> Self:
        """Create CrawlSites instance from file path to json input file"""

        records = json.loads(file.read_text(encoding="UTF-8"))
        crawl_sites = [CrawlSite(**record) for record in records]
        return cls(crawl_sites)

    def scheduled(self):
        """Yield only records that have a schedule"""
        yield from (crawl_site for crawl_site in self if crawl_site.schedule)
