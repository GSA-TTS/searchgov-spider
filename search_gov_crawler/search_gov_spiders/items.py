"""Define here the models for your scraped items
See documentation in:
https://docs.scrapy.org/en/latest/topics/items.html"""

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime

import scrapy


class SearchGovSpidersItem(scrapy.Item):
    """Class for Item which is a container for every returned scraped page"""

    response_bytes = scrapy.Field()
    url = scrapy.Field()
    output_target = scrapy.Field()
    response_language = scrapy.Field()
    content_type = scrapy.Field()

    def __repr__(self) -> str:
        """Override the default __repr__ so that we don't print the response_bytes which is very long sometimes."""

        return (
            f"Item(url={self.get('url')}, output_target={self.get('output_target')}, "
            f"content_type={self.get('content_type')}, response_language={self.get('response_language')})"
        )


@dataclass(kw_only=True)
class FreshnessSpiderException:
    """
    Class for the response from the freshness spider.  Used for both successful and failed URL checks.
    """

    exception_type: str = field(metadata={"template": {"type": "keyword"}})
    exception_message: str = field(metadata={"template": {"type": "text"}})


@dataclass(kw_only=True)
class FreshnessSpiderItem:
    """
    Base class for messages from Freshness Spider.  Used for both successful and failed URL checks.
    Also includes method to generate OpenSearch template based on dataclass fields and metadata.  This
    allows us to keep the template definition and item definition in one place, ensuring they are in sync.
    """

    checked_at: datetime = field(metadata={"template": {"type": "date"}})
    result: str = field(metadata={"template": {"type": "keyword"}})
    marked_for_deletion: bool = field(metadata={"template": {"type": "boolean"}})
    status_code: str | None = field(metadata={"template": {"type": "keyword"}})
    exception: FreshnessSpiderException | None
    index_name: str = field(metadata={"template": {"type": "keyword"}})
    id: str = field(metadata={"template": {"type": "keyword"}})
    path: str = field(metadata={"template": {"type": "keyword"}})
    domain_name: str = field(metadata={"template": {"type": "keyword"}})

    def to_dict(self) -> dict:
        """Convert dataclass to dict, including nested dataclass for exception."""
        return asdict(self)

    @classmethod
    def generate_template(cls) -> dict:
        """Generate OpenSearch template based on dataclass fields and metadata."""
        properties = {}
        for cls_field in fields(cls):
            if cls_field.name == "exception":
                exception_properties = {}
                for exc_cls_field in fields(FreshnessSpiderException):
                    if exc_cls_field_template := exc_cls_field.metadata.get("template"):
                        exception_properties[exc_cls_field.name] = exc_cls_field_template
                properties["exception"] = {"properties": exception_properties}
            elif cls_field_template := cls_field.metadata.get("template"):
                properties[cls_field.name] = cls_field_template

        return {
            "mappings": {"properties": properties},
            "settings": {"number_of_shards": 2, "number_of_replicas": 1},
        }


@dataclass(kw_only=True)
class FreshnessSpiderMarkedForDeletionItem(FreshnessSpiderItem):
    """
    Item for checks that produce status codes that are marked for deletion.
    """

    marked_for_deletion: bool = True
    exception: None = None


@dataclass(kw_only=True)
class FreshnessSpiderNotMarkedForDeletionItem(FreshnessSpiderItem):
    """
    Item for checks that produce status codes that are marked for deletion.
    """

    marked_for_deletion: bool = False
    exception: None = None


@dataclass(kw_only=True)
class FreshnessSpiderExceptionItem(FreshnessSpiderItem):
    """
    Item for an exception from the freshness spider.
    """

    marked_for_deletion: bool = False
    status_code: int | None = None
