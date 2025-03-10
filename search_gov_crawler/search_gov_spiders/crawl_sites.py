import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Self


@dataclass
class CrawlSite:
    """
    Represents a single crawl site record.  All fields required except schedule.
    In normal operations, When schedule is blank, a job will not be scheduled.  When running
    a benchmark, schedule is ignored.
    """

    name: str
    allow_query_string: bool
    allowed_domains: str
    handle_javascript: bool
    starting_urls: str
    output_target: str
    schedule: str | None = None

    def __post_init__(self):
        """Perform validation on record"""
        # check required fields
        missing_field_names = []
        for field in fields(self):
            if field.name == "schedule":
                pass
            elif getattr(self, field.name) is None:
                missing_field_names.append(field.name)

        if missing_field_names:
            msg = f"All CrawlSite fields are required!  Add values for {','.join(missing_field_names)}"
            raise TypeError(msg)

        # check types
        for field in fields(self):
            if not isinstance(getattr(self, field.name), field.type):
                msg = (
                    f"Invalid type! Field {field.name} with value {getattr(self, field.name)} must be type {field.type}"
                )
                raise TypeError(msg)

        # validate output_target values
        valid_output_targets = {"endpoint", "elasticsearch", "csv"}
        if self.output_target not in valid_output_targets:
            msg = f"Invalid output_target value {self.output_target}! Must be one of {valid_output_targets}"
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

        unique_sites = {(crawl_site.allowed_domains, crawl_site.starting_urls) for crawl_site in self.root}
        if len(unique_sites) != len(self.root):
            msg = "The combination of allowed_domain and starting_urls must be unique in file!"
            raise TypeError(msg)

    @classmethod
    def from_file(cls, file: Path) -> Self:
        """Create CrawlSites instance from file path to json input file"""

        records = json.loads(file.read_text(encoding="UTF-8"))
        crawl_sites = [CrawlSite(**record) for record in records]
        return cls(crawl_sites)

    def scheduled(self):
        """Yield only records that have a schedule"""
        yield from (crawl_site for crawl_site in self if crawl_site.schedule)
