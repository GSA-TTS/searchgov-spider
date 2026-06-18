import logging
import os

from pythonjsonlogger.json import JsonFormatter

from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT


def get_spider_logger(name: str) -> logging.Logger:
    """
    Get only one (and only) instance of search-gov spider logging

    Args:
        name: Namespace of the modual
    Returns:
        An instance of Logger
    """
    log = logging.getLogger(name)
    if not log.hasHandlers():
        log_level_str = os.environ.get("SCRAPY_LOG_LEVEL", "INFO")
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        log.setLevel(log_level)
        log.addHandler(logging.StreamHandler())
        log.handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
    log.propagate = False
    return log
