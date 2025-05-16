from typing import Self

from scrapy_redis import defaults
from scrapy_redis.connection import get_redis_from_settings
from scrapy_redis.dupefilter import RFPDupeFilter


class SearchGovSpiderRFPDupefilter(RFPDupeFilter):
    """
    Because we use domain_spider and domain_spider_js for different domains, we need to name the key with more
    than the spider name.
    """

    @classmethod
    def from_spider(cls, spider) -> Self:
        """
        Allow more unique naming for dupefilter keys.  Replicate everying from the parent class except
        the string substitution of the key name
        """
        settings = spider.settings
        server = get_redis_from_settings(settings)
        dupefilter_key = settings.get("SCHEDULER_DUPEFILTER_KEY", defaults.SCHEDULER_DUPEFILTER_KEY)
        debug = settings.getbool("DUPEFILTER_DEBUG")
        key = dupefilter_key % {"spider_id": spider.spider_id}  # Update dupefilter key with spider_id from spider
        return cls(server, key=key, debug=debug)
