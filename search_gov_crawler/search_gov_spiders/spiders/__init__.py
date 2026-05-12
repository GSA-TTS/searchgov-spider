# This package will contain the spiders of your Scrapy project
#
# Please refer to the documentation for information on how to create and manage
# your spiders.
from enum import StrEnum
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from .domain_spider import DomainSpider
    from .domain_spider_js import DomainSpiderJs

SearchGovDomainSpider = TypeVar("SearchGovDomainSpider", "DomainSpider", "DomainSpiderJs")


class SpiderStartedBy(StrEnum):
    """
    Represents the types of runs allowed when kicking off spiders.  Used for analytis and tracking.
    """

    MANUAL = "manual_run"
    SCHEDULED = "scheduled_spider"
    SITEMAP = "sitemap_spider"
