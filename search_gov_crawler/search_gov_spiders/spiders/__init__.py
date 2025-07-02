# This package will contain the spiders of your Scrapy project
#
# Please refer to the documentation for information on how to create and manage
# your spiders.
from typing import TypeVar

from .domain_spider import DomainSpider
from .domain_spider_js import DomainSpiderJs

SearchGovDomainSpider = TypeVar("SearchGovDomainSpider", DomainSpider, DomainSpiderJs)
