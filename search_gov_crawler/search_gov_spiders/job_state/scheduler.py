import scrapy.settings.default_settings as scrapy_defaults
from scrapy.settings import Settings
from scrapy.utils.misc import load_object
from scrapy_redis.scheduler import Scheduler


def disable_redis_job_state(settings: Settings) -> Settings:
    """Helper funciton to disable the scheduler and dupefilter redis functionality"""

    settings.set("SCHEDULER", scrapy_defaults.SCHEDULER)
    settings.set("DUPEFILTER_CLASS", scrapy_defaults.DUPEFILTER_CLASS)
    return settings


class SearchGovSpiderRedisScheduler(Scheduler):
    """Creates a customized version of the scrapy_redis scheduler that meets the needs of searchgov spider."""

    def open(self, spider) -> None:
        """
        Allow more unique naming for queue keys.  Replicate everying from the parent class except
        the string substitution of the key name.

        Added no cover markers since we don't need to test the code that comes from scrapy-redis, just our changes
        """

        self.spider = spider

        try:
            self.queue = load_object(self.queue_cls)(
                server=self.server,
                spider=spider,
                key=self.queue_key % {"spider": spider.spider_id},  # Update queue key with spider_id from spider
                serializer=self.serializer,
            )
        except TypeError as e:  # pragma: no cover
            msg = f"Failed to instantiate queue class '{self.queue_cls}': {e}"
            raise ValueError(msg) from e

        if not self.df:  # pragma: no cover
            self.df = load_object(self.dupefilter_cls).from_spider(spider)

        if self.flush_on_start:  # pragma: no cover
            self.flush()

        # notice if there are requests already in the queue to resume the crawl
        if len(self.queue):  # pragma: no cover
            spider.logger.info("Resuming crawl (%s requests scheduled)", len(self.queue))

    def close(self, reason: str) -> None:
        """
        Add better control over flushing of keys. Only when the spider closes because it is done or it is
        stopped using the closespider extension, flush the dupefilter key, otherwise follow rules in super method.
        """

        if reason == "finished" or reason.startswith("closespider_"):
            self.df.clear()

        super().close(reason)
