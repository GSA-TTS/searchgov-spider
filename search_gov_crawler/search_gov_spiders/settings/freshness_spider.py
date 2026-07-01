# These settings are for the freshness spider and represent the differences
# between the main `settings.py` and what is needed for the freshness spider.

# since we are making HEADS and checking on existing docs, we can go a little faster here
CONCURRENT_REQUESTS = 5
CONCURRENT_REQUESTS_PER_DOMAIN = 5
DOWNLOAD_DELAY = 0.25

# For the freshness spider, define custome middlewares, extensions, and item pipelines
DOWNLOADER_MIDDLEWARES = {"search_gov_spiders.middlewares.FreshnessSpiderDownloaderMiddleware": 100}
EXTENSIONS = {"search_gov_spiders.extensions.json_logging.JsonLogging": -1}
ITEM_PIPELINES = {"search_gov_spiders.pipelines.freshness_pipeline.FreshnessSpiderPipeline": 100}

# We actually care about errors, so let them all through
HTTPERROR_ALLOW_ALL = True

# Capture the fact of redirects, do not follow
REDIRECT_ENABLED = False

# We have alreay obeyed the robots.txt file during the inital spidering, this is not necessary
ROBOTSTXT_OBEY = False

# We don't need deduplication because our source is already dedupliated
DUPEFILTER_CLASS = "scrapy.dupefilters.BaseDupeFilter"
