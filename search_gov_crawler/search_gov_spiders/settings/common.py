# Scrapy settings for all search_gov_spiders spiders.  Only place settings here if they
# can apply to all spiders without affecting functionliaty.

import os

# Settings for logging and json logging
LOG_ENABLED = False
JSON_LOGGING_ENABLED = True
LOG_LEVEL = os.environ.get("SCRAPY_LOG_LEVEL", "INFO")

BOT_NAME = "search_gov_spiders"
SPIDER_MODULES = ["search_gov_spiders.spiders"]
NEWSPIDER_MODULE = "search_gov_spiders.spiders"

# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "usasearch"

# Disable telnet console since we don't use it
TELNETCONSOLE_ENABLED = False

COOKIES_ENABLED = False
REACTOR_THREADPOOL_MAXSIZE = 20
RETRY_ENABLED = False
DOWNLOAD_TIMEOUT = 15

# Limit downloads to 15MB
DOWNLOAD_MAXSIZE = 15728640

# default setting for how deep we want to go
DEPTH_LIMIT = 3

# crawl in BFO order rather than DFO
DEPTH_PRIORITY = 1
# These settings remain here to enable memory queue for testing and cases when we don't use redis
SCHEDULER_DISK_QUEUE = "scrapy.squeues.PickleFifoDiskQueue"
SCHEDULER_MEMORY_QUEUE = "scrapy.squeues.FifoMemoryQueue"

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = False

# Enable and configure HTTP caching (disabled by default)
# HTTPCACHE_ENABLED must be set to false for scrapy playwright to run
HTTPCACHE_ENABLED = False
HTTPCACHE_DIR = "httpcache"

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
