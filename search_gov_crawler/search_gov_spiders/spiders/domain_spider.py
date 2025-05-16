from scrapy.crawler import Crawler
from scrapy.http.response import Response
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders.crawl import CrawlSpider, Rule

import search_gov_crawler.search_gov_spiders.helpers.domain_spider as helpers
from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem


class DomainSpider(CrawlSpider):
    """
    Main spider for crawling and retrieving URLs.  Will grab single values for url and domain
    or use multiple comma-separated inputs.  If nothing is passed, it will crawl using the default list of
    domains and urls.  Supports path filtering of domains by extending the built-in OffsiteMiddleware. Has
    the ability to allow URLs with query string parameters if desired.

    Playwright javascript handling is disabled, use `domain_spider_js` for site that need to handle javascript.

    To use the CLI for crawling domain/site follow the pattern below.  The desired domains and urls can
    be either single values or comma separated lists. An optional allow_query_string parameter can also
    be passed. The default is false.

    `scrapy crawl domain_spider -a allowed_domains=<desired_domains> -a start_urls=<desired_urls>`

    Examples:
    Class Arguments
    - `allowed_domains="test-1.example.com,test-2.example.com"`
    - `start_urls="http://test-1.example.com/,https://test-2.example.com/"`
    - `output_target="csv"`

    - `allowed_domains="test-3.example.com"`
    - `start_urls="http://test-3.example.com/"`
    - `output_target="elasticsearch"`

    - `allow_query_string=true`
    - `allowed_domains="test-4.example.com"`
    - `start_urls="http://test-4.example.com/"`
    - `output_target="endpoint"`
    - `deny_paths="/tricky/path/,/another/tricky/path/"`

    CLI Usage
    - ```scrapy crawl domain_spider```
    - ```scrapy crawl domain_spider \
             -a allowed_domains=test-1.example.com,test-2.example.com \
             -a start_urls=http://test-1.example.com/,https://test-2.example.com/ \
             -a output_target=csv```
    - ```scrapy crawl domain_spider \
             -a allowed_domains=test-3.example.com \
             -a start_urls=http://test-3.example.com/ \
             -a output_target=endpoint```
    - ```scrapy crawl domain_spider \
             -a allow_query_string=true \
             -a allowed_domains=test-4.example.com \
             -a deny_paths=/tricky/path/,/another/tricky/path/ \
             -a start_urls=http://test-4.example.com/
             -a output_target=elasticsearch```
    """

    name: str = "domain_spider"

    def __init__(
        self,
        *args,
        allow_query_string: bool = False,
        allowed_domains: str | None = None,
        deny_paths: str | None = None,
        start_urls: str | None = None,
        output_target: str,
        prevent_follow: bool = False,
        **kwargs,
    ) -> None:
        helpers.validate_spider_arguments(allowed_domains, start_urls, output_target)

        # assign rules before super()__init__ so they can be processed by CrawlSpider
        if prevent_follow:
            self.rules = ()
            self.parse_start_url = self.parse_item
        else:
            self.rules = (
                Rule(
                    LinkExtractor(
                        allow=(),
                        deny=helpers.set_link_extractor_deny(deny_paths=deny_paths),
                        deny_extensions=helpers.FILTER_EXTENSIONS,
                        tags=helpers.LINK_TAGS,
                        unique=True,
                    ),
                    callback="parse_item",
                    follow=True,
                ),
            )
        super().__init__(*args, **kwargs)
        self.allow_query_string = allow_query_string
        self.output_target = output_target
        self.allowed_domains = (
            helpers.split_allowed_domains(allowed_domains)
            if allowed_domains
            else helpers.default_allowed_domains(handle_javascript=False)
        )
        self.allowed_domain_paths = (
            allowed_domains.split(",")
            if allowed_domains
            else helpers.default_allowed_domains(handle_javascript=False, remove_paths=False)
        )
        self.start_urls = (
            start_urls.split(",") if start_urls else helpers.default_starting_urls(handle_javascript=False)
        )

        # store input args as private attributes for use in logging
        self._deny_paths = deny_paths

        # create unique id to help with job state queues and elsewhere
        self.spider_id = helpers.generate_spider_id_from_args(self.allowed_domains, self.start_urls)

    @classmethod
    def from_crawler(cls, crawler: Crawler, *args, depth_limit: int | None = None, **kwargs) -> "DomainSpider":
        """
        Override default method to set DEPTH_LIMIT.  Default is set in settings.py file but can be overridden either by
        command line argument (-a depth_limit=x) or within a json scheduling file.
        """

        spider = super().from_crawler(crawler, *args, **kwargs)
        if int(depth_limit) > 250 or int(depth_limit) < 1:
            msg = f"Search Depth must be between 1 and 250 inclusive. You submitted: {depth_limit} "
            raise ValueError(msg)

        spider.settings.set("DEPTH_LIMIT", depth_limit, priority="spider")
        return spider

    def parse_item(self, response: Response):
        """
        This method is called by spiders to gather the url.  Placed in the spider to assist with
        testing and validtion.

        @url http://quotes.toscrape.com/
        @returns items 1 1
        @scrapes url
        """
        content_type_name = "Content-Type"
        content_type_value = response.headers.get(
            content_type_name, response.headers.get(content_type_name.lower(), None)
        )
        if helpers.is_valid_content_type(content_type_value, output_target=self.output_target):
            yield SearchGovSpidersItem(
                url=response.url,
                response_bytes=response.body,
                output_target=self.output_target,
                content_type=helpers.get_simple_content_type(content_type_value, output_target=self.output_target),
            )
