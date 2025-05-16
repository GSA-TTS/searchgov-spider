# Scrapy settings for search_gov_spiders project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import os
from datetime import UTC, datetime
from pathlib import Path

from search_gov_crawler.scheduling.redis import get_redis_connection_args

spider_start = datetime.now(tz=UTC)

# Settings for logging and json logging
LOG_ENABLED = False
JSON_LOGGING_ENABLED = True
LOG_LEVEL = os.environ.get("SCRAPY_LOG_LEVEL", "INFO")

BOT_NAME = "search_gov_spiders"
SPIDER_MODULES = ["search_gov_spiders.spiders"]
NEWSPIDER_MODULE = "search_gov_spiders.spiders"

# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "usasearch"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Disable telnet console since we don't use it
TELNETCONSOLE_ENABLED = False

COOKIES_ENABLED = False
REACTOR_THREADPOOL_MAXSIZE = 20
RETRY_ENABLED = False
DOWNLOAD_TIMEOUT = 15

# Close spider if no URLs found in period
CLOSESPIDER_TIMEOUT_NO_ITEM = 60 * 60 * 24  # 24 hours in seconds

# Enforce slow crawling
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 1

# Limit downloads to 15MB
DOWNLOAD_MAXSIZE = 15728640

# settings for broad crawling
SCHEDULER_PRIORITY_QUEUE = "scrapy.pqueues.DownloaderAwarePriorityQueue"
# set to True for BFO
AJAXCRAWL_ENABLED = True

# default setting for how deep we want to go
DEPTH_LIMIT = 3

# crawl in BFO order rather than DFO
DEPTH_PRIORITY = 1

# Enable requests scheduler and dupefilter in redis using scrapy-redis
# See https://github.com/rmax/scrapy-redis/wiki/Usage
redis_connection_args = get_redis_connection_args()
REDIS_HOST = redis_connection_args["host"]
REDIS_PORT = redis_connection_args["port"]
REDIS_DB = redis_connection_args["db"]

SCHEDULER = "search_gov_spiders.job_state.scheduler.SearchGovSpiderRedisScheduler"
DUPEFILTER_CLASS = "search_gov_spiders.job_state.dupefilter.SearchGovSpiderRFPDupefilter"

SCHEDULER_PERSIST = True
SCHEDULER_QUEUE_KEY = "spider.%(spider_id)s.requests"
SCHEDULER_QUEUE_CLASS = "search_gov_spiders.job_state.queue.SearchGovSpiderFifoQueue"
SCHEDULER_DUPEFILTER_KEY = "spider.%(spider_id)s.dupefilter"
SCHEDULER_KEY_ORPHAN_AGE = 604800  # one week in seconds

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
SPIDER_MIDDLEWARES = {
    "search_gov_spiders.middlewares.SearchGovSpidersSpiderMiddleware": 543,
}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    "search_gov_spiders.middlewares.SearchGovSpidersOffsiteMiddleware": 100,
    "search_gov_spiders.middlewares.SearchGovSpidersDownloaderMiddleware": 543,
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
EXTENSIONS = {
    "search_gov_spiders.extensions.json_logging.JsonLogging": -1,
    "search_gov_spiders.extensions.scheduler_queue.RedisSchedulerQueue": 500,
    "spidermon.contrib.scrapy.extensions.Spidermon": 600,
}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "search_gov_spiders.pipelines.DeDeuplicatorPipeline": 100,
    "search_gov_spiders.pipelines.SearchGovSpidersPipeline": 200,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = False


# Enable and configure HTTP caching (disabled by default)
# HTTPCACHE_ENABLED must be set to false for scrapy playwright to run
HTTPCACHE_ENABLED = False
HTTPCACHE_DIR = "httpcache"

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# SPIDERMON SETTINGS
SPIDERMON_ENABLED = os.environ.get("SPIDER_SPIDERMON_ENABLED", "True")
SPIDERMON_EXPECTED_FINISH_REASONS = ["finished"]
SPIDERMON_MIN_ITEMS = 1
SPIDERMON_MAX_EXECUTION_TIME = 172800  # 48 hours in seconds
SPIDERMON_SPIDER_CLOSE_MONITORS = ("search_gov_spiders.monitors.SpiderCloseMonitorSuite",)
SPIDERMON_UNWANTED_HTTP_CODES_MAX_COUNT = 50
SPIDERMON_UNWANTED_HTTP_CODES = [400, 407, 429, 500, 502, 503, 504, 523, 540, 541]

SPIDER_URLS_API = os.environ.get("SPIDER_URLS_API", "https://local.search.usa.gov/urls")
url_portion = SPIDER_URLS_API.split("https://")[1].split(".")[0]
env_name = "prod" if url_portion == "search" else url_portion

SPIDERMON_BODY_HTML_TEMPLATE = Path(__file__).parent / "actions" / "results.jinja"
SPIDERMON_REPORT_CONTEXT = {"report_title": "Spidermon File Report"}
SPIDERMON_REPORT_FILENAME = f"{spider_start.isoformat()}_spidermon_file_report.html"
SPIDERMON_REPORT_TEMPLATE = "results.jinja"

SPIDERMON_AWS_ACCESS_KEY_ID = os.environ.get("SEARCH_AWS_ACCESS_KEY_ID")
SPIDERMON_AWS_SECRET_ACCESS_KEY = os.environ.get("SEARCH_AWS_SECRET_ACCESS_KEY")
SPIDERMON_AWS_REGION_NAME = "us-east-1"
SPIDERMON_EMAIL_SUBJECT = f"{env_name} Spidermon Report".capitalize()
SPIDERMON_EMAIL_SENDER = "search@support.digitalgov.gov"
SPIDERMON_EMAIL_TO = "tts-search-devs@gsa.gov"
