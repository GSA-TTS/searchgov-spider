import logging
from typing import Self

from pythonjsonlogger.json import JsonFormatter
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured
from scrapy.signals import spider_opened
from scrapy.spiders import Spider

LOG_FMT = "%(asctime)%(name)%(levelname)%(message)"
SITEMAP_START_URLS = "Generated from Sitemap"


def search_gov_default(obj) -> dict | None:
    """Function to help serialize scrapy objects in logs"""
    if isinstance(obj, Spider):
        return {
            "name": obj.name,
            "allow_query_string": getattr(obj, "allow_query_string", None),
            "allowed_domains": getattr(obj, "allowed_domains", None),
            "allowed_domain_paths": getattr(obj, "allowed_domain_paths", None),
            "start_urls": SITEMAP_START_URLS if getattr(obj, "_prevent_follow", None) else obj.start_urls,
            "output_target": getattr(obj, "output_target", None),
            "depth_limit": obj.settings.get("DEPTH_LIMIT", None),
            "deny_paths": getattr(obj, "_deny_paths", None),
        }

    if isinstance(obj, Crawler):
        return {"name": str(obj.settings.get("BOT_NAME", "Unknown"))}

    return None


class SearchGovSpiderStreamHandler(logging.StreamHandler):
    """Extension of logging.StreamHandler with our level, fmt, and defaults"""

    def __init__(self, log_level, *_args, **_kwargs):
        super().__init__(*_args, **_kwargs)
        formatter = JsonFormatter(fmt=LOG_FMT, json_default=search_gov_default)
        self.setLevel(log_level)
        self.setFormatter(formatter)


class SearchGovSpiderFileHandler(logging.FileHandler):
    """Extension of logging.File with our level, fmt, and defaults"""

    def __init__(self, log_level, *args, **kwargs):
        super().__init__(*args, **kwargs)
        formatter = JsonFormatter(fmt=LOG_FMT, json_default=search_gov_default)
        self.setLevel(log_level)
        self.setFormatter(formatter)

    @classmethod
    def from_hanlder(cls, handler: logging.FileHandler, log_level: str) -> "SearchGovSpiderFileHandler":
        """Create a json file handler based on values used by an existing FileHandler"""

        new_filename = handler.baseFilename if handler.baseFilename == "/dev/null" else f"{handler.baseFilename}.json"

        return cls(
            log_level=log_level,
            filename=new_filename,
            mode=handler.mode,
            encoding=handler.encoding,
            delay=handler.delay,
            errors=handler.errors,
        )


class JsonLogging:
    """Scrapy extension that injects JSON logging into a spider run."""

    file_hanlder_enabled: bool
    log_level: str

    def __init__(self, log_level):
        self.file_hanlder_enabled = False
        self.stream_handler_enabled = False
        self.log_level = log_level
        self._add_json_handlers()

    def _add_json_handlers(self) -> None:
        """Try to add json hanlders for file and streaming"""

        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)

        if not self.file_hanlder_enabled:
            file_handlers = [handler for handler in root_logger.handlers if isinstance(handler, logging.FileHandler)]

            for file_handler in file_handlers:
                root_logger.addHandler(
                    SearchGovSpiderFileHandler.from_hanlder(handler=file_handler, log_level=self.log_level),
                )
                self.file_hanlder_enabled = True

        if not self.stream_handler_enabled:
            standard_stream_handlers = [
                handler for handler in root_logger.handlers if handler.__class__ == logging.StreamHandler
            ]

            for handler in standard_stream_handlers:
                root_logger.removeHandler(handler)

            self.stream_handler_enabled = True

        if not any(handler for handler in root_logger.handlers if isinstance(handler, SearchGovSpiderStreamHandler)):
            root_logger.addHandler(SearchGovSpiderStreamHandler(log_level=self.log_level))

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        """
        Required extension method that checks for configuration and connects extension methons to signals
        """
        if not crawler.settings.getbool("JSON_LOGGING_ENABLED"):
            msg = "JsonLogging extension is listed in settings.EXTENSIONS but is not enabled."
            raise NotConfigured(msg)

        ext = cls(log_level=crawler.settings.get("LOG_LEVEL", "INFO"))
        crawler.signals.connect(ext.spider_opened, signal=spider_opened)
        return ext

    def spider_opened(self, spider: Spider) -> None:
        """Try to add hanlders and then log arguments passed to the spider"""

        self._add_json_handlers()
        spider.logger.info(
            (
                "Starting spider %s with following args: "
                "allowed_domains=%s allowed_domain_paths=%s start_urls=%s "
                "output_target=%s depth_limit=%s deny_paths=%s"
            ),
            spider.name,
            ",".join(getattr(spider, "allowed_domains", [])),
            ",".join(getattr(spider, "allowed_domains_paths", [])),
            SITEMAP_START_URLS if getattr(spider, "_prevent_follow", None) else ",".join(spider.start_urls),
            getattr(spider, "output_target", None),
            spider.settings.get("DEPTH_LIMIT", None),
            getattr(spider, "_deny_paths", None),
        )
