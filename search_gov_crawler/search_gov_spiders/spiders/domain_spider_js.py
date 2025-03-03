from scrapy.http.request import Request
from scrapy.http.response import Response
from scrapy.spiders.crawl import CrawlSpider, Rule

import search_gov_crawler.search_gov_spiders.helpers.domain_spider as helpers
from search_gov_crawler.search_gov_spiders.helpers import encoding
from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem


def should_abort_request(request):
    """Helper function to tell playwright if it should process requests based on resource type"""

    return request.resource_type in helpers.FILTER_EXTENSIONS


class DomainSpiderJs(CrawlSpider):
    """
    Main spider for crawling and retrieving URLs using a headless browser to hanlde javascript.
    Will grab single values for url and domain or use multiple comma-separated inputs.
    If nothing is passed, it will crawl using the default list of domains and urls.  Supports path
    filtering of domains by extending the built-in OffsiteMiddleware.  Has the ability to allow URLs
    with query string parameters if desired.

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
    - `output_target="elasticsearch"`

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
             -a output_target=elasticsearch```
    - ```scrapy crawl domain_spider \
             -a allow_query_string=true \
             -a allowed_domains=test-4.example.com \
             -a start_urls=http://test-4.example.com/
             -a output_target=csv```
    """

    name: str = "domain_spider_js"
    rules = (
        Rule(
            link_extractor=helpers.domain_spider_link_extractor,
            callback="parse_item",
            follow=True,
            process_request="set_playwright_usage",
        ),
    )

    @classmethod
    def update_settings(cls, settings):
        """Moved settings update to this classmethod due to complexity."""

        super().update_settings(settings)
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

    def __init__(
        self,
        *args,
        allow_query_string: bool = False,
        allowed_domains: str | None = None,
        start_urls: str | None = None,
        output_target: str,
        **kwargs,
    ) -> None:
        helpers.validate_spider_arguments(allowed_domains, start_urls, output_target)

        super().__init__(*args, **kwargs)

        self.allow_query_string = allow_query_string

        self.allowed_domains = (
            helpers.split_allowed_domains(allowed_domains)
            if allowed_domains
            else helpers.default_allowed_domains(handle_javascript=True)
        )

        self.allowed_domain_paths = (
            allowed_domains.split(",")
            if allowed_domains
            else helpers.default_allowed_domains(handle_javascript=True, remove_paths=False)
        )
        self.start_urls = start_urls.split(",") if start_urls else helpers.default_starting_urls(handle_javascript=True)
        self.output_target = output_target

    def parse_item(self, response: Response):
        """
        This method is called by spiders to gather the url.  Placed in the spider to assist with
        testing and validtion.

        @url http://quotes.toscrape.com/
        @returns items 1 1
        @scrapes url
        """

        if helpers.is_valid_content_type(response.headers.get("content-type", None), output_target=self.output_target):
            html_content = encoding.decode_http_response(response_bytes=response.body)
            yield SearchGovSpidersItem(url=response.url, html_content=html_content, output_target=self.output_target)

    def set_playwright_usage(self, request: Request, _response: Response) -> Request:
        """Set meta tags for playwright to run"""

        request.meta["playwright"] = True
        return request
