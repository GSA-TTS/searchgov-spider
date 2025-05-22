import logging
from pathlib import Path
from typing import Self

from redis import Redis
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured
from scrapy.signals import spider_closed
from scrapy.spiders import Spider

from search_gov_crawler.scheduling.redis import init_redis_client


class OnDiskSchedulerQueue:
    """Custom scrapy extension that helps clean up the on-disk scheduler queue directory when a spider is finished"""

    setting_key: str = "JOBDIR"

    def remove_directory(self, directory: Path) -> None:
        """Recusrively remove a directory and contents"""

        for item in directory.iterdir():
            if item.is_dir():
                self.remove_directory(item)
            else:
                item.unlink()

        directory.rmdir()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        """
        Required extension method that checks for configuration and connects extension methons to signals
        """
        if not crawler.settings.get(cls.setting_key):
            msg = f"OnDiskSchedulerQueue extension is listed in settings.EXTENSIONS but {cls.setting_key} is not set."
            raise NotConfigured(msg)

        ext = cls()
        crawler.signals.connect(ext.spider_closed, signal=spider_closed)
        return ext

    def spider_closed(self, spider: Spider) -> None:
        """Clean up jobs directory when spider is finished"""

        spider_log = logging.getLogger(spider.name)
        job_dir = spider.settings.get(self.setting_key)
        self.remove_directory(Path(job_dir))
        spider_log.info("Removed %s %s at end of spider.", self.setting_key, job_dir)


class RedisSchedulerQueue:
    """Custom scrapy extension to help with cleanup of orphaned job state queues"""

    setting_key: str = "SCHEDULER_PERSIST"
    scheduler_queue_key: str = "SCHEDULER_QUEUE_KEY"
    dupefilter_queue_key: str = "SCHEDULER_DUPEFILTER_KEY"
    orphan_age_key: str = "SCHEDULER_KEY_ORPHAN_AGE"

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        """
        Required extension method that checks for configuration and connects extension methons to signals
        """
        if not crawler.settings.getbool(cls.setting_key):
            msg = f"RedisSchedulerQueue extension is listed in settings.EXTENSIONS but {cls.setting_key} is not True."
            raise NotConfigured(msg)

        if not crawler.settings.get(cls.orphan_age_key):
            msg = f"RedisSchedulerQueue extension is listed in settings.EXTENSIONS but {cls.orphan_age_key} is not set."
            raise NotConfigured(msg)

        if not (crawler.settings.get(cls.dupefilter_queue_key) and crawler.settings.get(cls.scheduler_queue_key)):
            msg = (
                "RedisSchedulerQueue extension is listed in settings.EXTENSIONS but "
                f"{cls.dupefilter_queue_key} or {cls.scheduler_queue_key} is not set"
            )
            raise NotConfigured(msg)

        ext = cls()
        crawler.signals.connect(ext.spider_closed, signal=spider_closed)
        return ext

    @staticmethod
    def _is_orphan_key(redis: Redis, orphan_age: int, key: str) -> bool:
        """Compare idle time to orphan age, return true if key is an orphan"""

        idletime = redis.object(infotype="idletime", key=key)
        if idletime:
            return int(idletime) > orphan_age

        return False

    def spider_closed(self, spider: Spider) -> None:
        """
        On spider close, check for orphaned scheduler related keys based on how long it has been
        since they were accessed.
        """

        scheduler_key = spider.settings.get(self.scheduler_queue_key)
        dupefilter_key = spider.settings.get(self.dupefilter_queue_key)
        orphan_age = spider.settings.getint(self.orphan_age_key)

        scheduler_key_pattern = scheduler_key % {"spider": "*"}
        dupefilter_key_pattern = dupefilter_key % {"spider": "*"}

        redis = init_redis_client(charset="utf-8", decode_responses=True)
        orphan_keys = [
            key
            for key in redis.scan_iter(scheduler_key_pattern)
            if self._is_orphan_key(redis=redis, orphan_age=orphan_age, key=key)
        ]
        orphan_keys.extend(
            key
            for key in redis.scan_iter(dupefilter_key_pattern)
            if self._is_orphan_key(redis=redis, orphan_age=orphan_age, key=key)
        )

        if orphan_keys:
            redis.delete(*orphan_keys)
            spider.logger.info("Found and deleted %s orphan keys!", len(orphan_keys))
