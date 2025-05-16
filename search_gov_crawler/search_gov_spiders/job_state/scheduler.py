from scrapy.utils.misc import load_object
from scrapy_redis.scheduler import Scheduler


class SearchGovSpiderRedisScheduler(Scheduler):
    """Creates a customized version of the scrapy_redis scheduler that meets the needs of searchgov spider."""

    def open(self, spider) -> None:
        """
        Allow more unique naming for queue keys.  Replicate everying from the parent class except
        the string substitution of the key name
        """

        self.spider = spider

        try:
            self.queue = load_object(self.queue_cls)(
                server=self.server,
                spider=spider,
                key=self.queue_key % {"spider_id": spider.spider_id},  # Update queue key with spider_id from spider
                serializer=self.serializer,
            )
        except TypeError as e:
            msg = f"Failed to instantiate queue class '{self.queue_cls}': {e}"
            raise ValueError(msg) from e

        if not self.df:
            self.df = load_object(self.dupefilter_cls).from_spider(spider)

        if self.flush_on_start:
            self.flush()

        # notice if there are requests already in the queue to resume the crawl
        if len(self.queue):
            spider.logger.info("Resuming crawl (%s requests scheduled)", len(self.queue))

    def close(self, reason: str) -> None:
        """
        Add better control over flushing of keys. Only when the spider closes because it is done or it is
        stopped using the closespider extension, flush the dupefilter key, otherwise follow rules in super method.
        """

        if reason == "finished" or reason.startswith("closespider_"):
            self.df.clear()

        super().close(reason)
