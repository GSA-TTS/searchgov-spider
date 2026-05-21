from scrapy.crawler import Crawler
from scrapy.http.request import Request
from scrapy.http.response import Response
from scrapy.linkextractors import LinkExtractor
from scrapy.settings import BaseSettings
from scrapy.spiders.crawl import CrawlSpider, Rule

import search_gov_crawler.search_gov_spiders.helpers.domain_spider as helpers
from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem
from search_gov_crawler.search_gov_spiders.spiders import SpiderStartedBy


def should_abort_request(request):
    """Helper function to tell playwright if it should process requests based on resource type"""

    return request.resource_type in helpers.FILTER_EXTENSIONS


class DomainSpiderJs(CrawlSpider):
    """
    Main spider for crawling and retrieving URLs using a headless browser to hanlde javascript.
    Will grab single values for url and domain or use multiple comma-separated inputs.
    Supports path filtering of domains by extending the built-in OffsiteMiddleware.  Has the
    ability to allow URLs with query string parameters if desired.

    Playwright javascript handling is enabled and resource intensive, only use if needed.  For crawls
    that don't require html, use `domain_spider`.

    To use the CLI for crawling domain/site follow the pattern below.  The desired domains and urls can
    be either single values or comma separated lists. An optional allow_query_string parameter can also
    be passed. The default is false.

    ```scrapy crawl domain_spider\
        -a allowed_domains=<desired_domains>\
        -a start_urls=<desired_urls>\
        -a output_target=<desired_output_target>```

    Examples:
    Class Arguments
    - `allowed_domains="test-1.example.com,test-2.example.com"`
    - `start_urls="http://test-1.example.com/,https://test-2.example.com/"`
    - `output_target="csv"`

    - `allowed_domains="test-3.example.com"`
    - `start_urls="http://test-3.example.com/"`
    - `output_target="opensearch"`

    - `allow_query_string=true`
    - `allowed_domains="test-4.example.com"`
    - `start_urls="http://test-4.example.com/"`
    - `output_target="endpoint"`

    CLI Usage
    - `scrapy crawl domain_spider_js -a output_target=csv`
    - ```scrapy crawl domain_spider_js \
             -a allowed_domains=test-1.example.com,test-2.example.com \
             -a start_urls=http://test-1.example.com/,https://test-2.example.com/\
             -a output_target=csv```
    - ```scrapy crawl domain_spider \
             -a allowed_domains=test-3.example.com \
             -a start_urls=http://test-3.example.com/
             -a output_target=opensearch```
    - ```scrapy crawl domain_spider \
             -a allow_query_string=true \
             -a allowed_domains=test-4.example.com \
             -a start_urls=http://test-4.example.com/
             -a output_target=csv```
    """

    name: str = "domain_spider_js"

    def __init__(
        self,
        *args,
        allow_query_string: bool = False,
        allowed_domains: str,
        deny_paths: str | None = None,
        output_target: str,
        sitemap_url: str | None = None,
        start_urls: str,
        started_by: str = SpiderStartedBy.MANUAL.value,
        **kwargs,
    ) -> None:
        helpers.validate_spider_arguments(allowed_domains, start_urls, sitemap_url, output_target)

        # assign rules before super()__init__ so they can be processed by CrawlSpider
        if not sitemap_url:
            self.rules = (
                Rule(
                    link_extractor=LinkExtractor(
                        allow=(),
                        deny=helpers.set_link_extractor_deny(deny_paths=deny_paths),
                        deny_extensions=helpers.FILTER_EXTENSIONS,
                        tags=helpers.LINK_TAGS,
                        unique=True,
                    ),
                    callback="parse_item",
                    follow=True,
                    process_request="update_request_meta",
                ),
            )

        super().__init__(*args, **kwargs)
        self.allow_query_string = helpers.force_bool(allow_query_string)
        self.allowed_domains = helpers.split_allowed_domains(allowed_domains)
        self.allowed_domain_paths = allowed_domains.split(",")
        self.start_urls = start_urls.split(",")
        self.output_target = output_target
        self.started_by = started_by

        # store input args as private attributes for use in logging
        self._deny_paths = deny_paths
        self._sitemap_url = sitemap_url

        # gather domain visits for domain and subdomains
        self.domain_visits = helpers.get_domain_visits(self)

        # create unique id to help with job state queues and elsewhere
        self.spider_id = helpers.generate_spider_id_from_args(
            self.name,
            self.allowed_domains,
            self.start_urls,
            self.is_sitemap_crawl,
        )

    @classmethod
    def from_crawler(cls, crawler: Crawler, *args, depth_limit: int | None = None, **kwargs) -> "DomainSpiderJs":
        """
        Override default method to set DEPTH_LIMIT.  Default is set in settings.py file but can be overridden either by
        command line argument (-a depth_limit=x) or within a json scheduling file.
        """
        max_depth_limit = 250

        spider = super().from_crawler(crawler, *args, **kwargs)
        if int(depth_limit) > max_depth_limit or int(depth_limit) < 1:
            msg = f"Search Depth must be between 1 and 250 inclusive. You submitted: {depth_limit} "
            raise ValueError(msg)

        spider.settings.set("DEPTH_LIMIT", depth_limit, priority="spider")
        return spider

    @property
    def is_sitemap_crawl(self):
        """Check for existence of sitemap url"""
        return bool(self._sitemap_url)

    def parse_item(self, response: Response):
        """
        This method is called by spiders to gather the url.  Placed in the spider to assist with
        testing and validtion.

        @url http://quotes.toscrape.com/
        @returns items 1 1
        @scrapes url
        """

        if content_type := helpers.get_simple_content_type(response=response, output_target=self.output_target):
            yield SearchGovSpidersItem(
                content_type=content_type,
                creator=self.started_by,
                crawl_depth=response.meta.get("depth") if not self.is_sitemap_crawl else 1,
                download_milliseconds=helpers.get_download_milliseconds(response=response),
                output_target=self.output_target,
                response_bytes=response.body,
                response_language=helpers.get_response_language_code(response=response),
                source_url=response.request.meta.get("source_url") if response.request else None,
                url=response.url,
            )

    def parse_start_url(self, response: Response, **_kwargs):
        """
        When this is a sitemap crawl is enabled, add sitemap url to start urls responses otherwise
        skip as this is handled elsewhere
        """

        if self.is_sitemap_crawl:
            if response.request:
                response.request.meta["source_url"] = self._sitemap_url

            return self.parse_item(response=response)

        return ()

    def update_request_meta(self, request: Request, response: Response) -> Request:
        """
        Add the source url to the request meta field for inclusion in the item and
        set meta tags for playwright to run
        """

        request.meta["playwright"] = True
        if response.request:
            request.meta["source_url"] = response.request.url

        return request

    @classmethod
    def update_settings(cls, settings: BaseSettings):
        """
        Apply project-wider common settings as well as custom settings at the spider priority level
        for just this spider.
        """

        super().update_settings(settings)
        settings.setmodule(module="search_gov_crawler.search_gov_spiders.settings.domain_spider", priority="spider")

        # domain_spider_js specific settings
        settings.set("PLAYWRIGHT_ABORT_REQUEST", should_abort_request, priority="spider")
        settings.set("PLAYWRIGHT_BROWSER_TYPE", "chromium", priority="spider")
        settings.set("PLAYWRIGHT_LAUNCH_OPTIONS", {"headless": True}, priority="spider")
        settings.set(
            "DOWNLOAD_HANDLERS",
            {
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
            priority="spider",
        )
