from scrapy_redis.queue import FifoQueue


class SearchGovSpiderFifoQueue(FifoQueue):
    """Subclass the scrapy_redis FifoQueue so that we can use the spider_id to name redis keys"""

    def __init__(self, server, spider, key, serializer=None) -> None:
        """
        Allow more unique naming for queue keys.  Call parent __init__ and then replace the key
        value with one that uses spider_id.
        """

        super().__init__(server, spider, key, serializer)
        self.key = key % {"spider": spider.spider_id}  # Update queue key with spider_id from spider
