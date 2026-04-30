import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Self

from apscheduler.triggers.cron import CronTrigger


class FreshnessCheckerValidationError(Exception):
    """Custom exception for freshness checker config validation errors."""


@dataclass(kw_only=True)
class FreshnessCheckerConfig:
    """
    Configuration class for a freshness checker job.
    """

    name: str
    schedule: str
    query: dict
    max_results: str

    def __post_init__(self):
        """Peform type validations"""
        self.max_results = str(self.max_results or "")
        self._type_validation()
        self._validate_schedule()

    def _type_validation(self) -> None:
        """Check field types against class definition to ensure compatibility"""

        for field in fields(self):
            if not isinstance(getattr(self, field.name), field.type):
                msg = (
                    f"Invalid type! Field `{field.name}` with "
                    f"value {getattr(self, field.name)} must be type {field.type}"
                )
                raise FreshnessCheckerValidationError(msg)

    def _validate_schedule(self) -> None:
        """Validate schedule is cron expression"""

        if self.schedule:
            try:
                CronTrigger.from_crontab(self.schedule)
            except ValueError as err:
                msg = f"Invalid cron expression in schedule: {self.schedule}"
                raise FreshnessCheckerValidationError(msg) from err


@dataclass
class FreshnessCheckerConfigs:
    """Represents a list of crawl config records"""

    root: list[FreshnessCheckerConfig]

    def __iter__(self):
        """Iterate directly from FreshnessCheckerConfig instance instead of calling root."""
        yield from self.root

    @classmethod
    def from_file(cls, file: Path) -> Self:
        """Create FreshnessCheckerConfig instance from file path to json input file"""

        records = json.loads(file.read_text(encoding="UTF-8"))
        crawl_configs = [FreshnessCheckerConfig(**record) for record in records]
        return cls(crawl_configs)
