"""Define here the models for your spider middleware

See documentation in:
https://docs.scrapy.org/en/latest/topics/spider-middleware.html
"""

import re
import warnings
from collections.abc import Iterator
from typing import Any, Self
from urllib.parse import urlparse

from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.downloadermiddlewares.offsite import OffsiteMiddleware
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Request, Response
from scrapy.spidermiddlewares.base import BaseSpiderMiddleware
from scrapy.spiders import Spider
from scrapy.utils.httpobj import urlparse_cached

from search_gov_crawler.search_gov_spiders.items import SearchGovSpidersItem


class SearchgovMiddlewareBase(BaseSpiderMiddleware):
    """Base middleware class that spider middlewares extend"""

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        """This method is used by Scrapy to create your spiders."""
        s = cls(crawler)
        s.crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def spider_opened(self, spider: Spider):  # pylint: disable=unused-argument
        """Placeholder method in Middleware.  Called when spider starts. Override in subclass if needed."""


class SearchGovSpidersSpiderMiddleware(SearchgovMiddlewareBase):
    """
    Custom search gov spider middleare.  Not all methods need to be defined. If a method is not defined,
    scrapy acts as if the spider middleware does not modify the passed objects.
    """

    def _filter_url_query_string(self, url: str | None) -> bool:
        """Private helper function to filter urls by existence of query string (if applicable)"""

        if getattr(self.crawler.spider, "allow_query_string", False):
            return False

        if urlparse(url).query:
            msg = f"Filtering URL with query string: {url}"
            self.crawler.spider.logger.debug(msg)
            return True

        return False

    def _remove_url_jsession_id(self, url: str | None) -> str | None:
        """Private helper function to filter urls by existence of JSESSIONID (if applicable)"""

        parse_result = urlparse(url)
        if "jsessionid" in parse_result.params.lower():
            url = parse_result._replace(params="").geturl()

        return url

    # pylint: disable=unused-argument
    # disable unused arguments in this scrapy-generated class template

    def process_spider_input(self, response: Response) -> None:
        """
        Called for each response that goes through the spider middleware and into the spider.

        Should return None or raise an exception.
        """
        return

    def process_spider_output(self, response: Response, result: Iterator[Any]):
        """Called with the results returned from the Spider, after it has processed the response.

        Must return an iterable of Request, or item objects.
        """
        yield from result

    def process_spider_exception(self, response: Response, exception) -> None:
        """Called when a spider or process_spider_input() method
        (from other spider middleware) raises an exception.

        Should return either None or an iterable of Request or item objects.
        """
        if response.request.meta.get("is_start_request", False):
            self.crawler.spider.logger.exception(
                "Error occured while accessing start url: %s: response: %s, %s",
                response.request.url,
                response,
                exception,
            )

    def get_processed_request(self, request: Request, response: Response | None) -> Request | None:
        """Return a processed request from the spider output.

        This method is called with a single request from the start seeds or the
        spider output. It should return the same or a different request, or
        ``None`` to ignore it.

        :param request: the input request
        :type request: :class:`~scrapy.Request` object

        :param response: the response being processed
        :type response: :class:`~scrapy.http.Response` object or ``None`` for
            start seeds

        :return: the processed request or ``None``

        Logic should be placed here so that requests are prevented from going into the scheduler.
        """
        if request.dont_filter:
            return request

        if self._filter_url_query_string(url=request.url):
            return None

        if "jsessionid" in request.url.lower():
            request = request.replace(url=self._remove_url_jsession_id(url=request.url))

        return request

    def get_processed_item(self, item: SearchGovSpidersItem, response: Response | None) -> Any:
        """Return a processed item from the spider output.

        This method is called with a single item from the start seeds or the
        spider output. It should return the same or a different item, or
        ``None`` to ignore it.

        :param item: the input item
        :type item: item object

        :param response: the response being processed
        :type response: :class:`~scrapy.http.Response` object or ``None`` for
            start seeds

        :return: the processed item or ``None``

        Here we also have to check for URLs with query strings because the spider middleware
        can return both items and requests.
        """
        if response and response.request.dont_filter:
            return item

        item_url = item.get("url", "")
        if self._filter_url_query_string(url=item_url):
            return None

        if "jsessionid" in item_url.lower():
            item["url"] = self._remove_url_jsession_id(url=item_url)

        return item


class SearchGovSpidersDownloaderMiddleware:
    """
    Custom search gov spider downloader middleare.  Placeholder for now.
    See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#downloader-middleware for
    usage instructions.

    Not all methods need to be defined. If a method is not defined, scrapy acts as if the downloader
    middleware does not modify the passed objects.
    """

    # pylint: disable=unused-argument
    # disable unused arguments in this scrapy-generated class template
    def process_request(self, request: Request) -> None:
        """
        Called for each request that goes through the downloader middleware.  Ignore
        requests that contain query params except if the spider specifically allows it.

        Must either:
          - return None: continue processing this request
          - or return a Response object
          - or return a Request object
          - or raise IgnoreRequest: process_exception() methods of installed
            downloader middleware will be called
        """
        return

    def process_response(self, request: Request, response: Response) -> Response:
        """
        Called with the response returned from the downloader.

        Must either;
          - return a Response object
          - return a Request object
          - or raise IgnoreRequest
        """
        return response

    def process_exception(self, request: Request, exception):
        """
        Called when a download handler or a process_request() (from other downloader middleware)
        raises an exception.

        Must either:
          - return None: continue processing this exception
          - return a Response object: stops process_exception() chain
          - return a Request object: stops process_exception() chain
        """
        return


class SearchGovSpidersOffsiteMiddleware(OffsiteMiddleware):
    """Extend OffsiteMiddleware to enable filtering of paths as well as domains"""

    host_regex: re.Pattern
    host_path_regex: re.Pattern

    def spider_opened(self, spider: Spider) -> None:
        """Overridden to add assignment of host_path_regex"""
        self.host_regex = self.get_host_regex(spider)
        self.host_path_regex = self.get_host_path_regex(spider)

    def should_follow(self, request: Request, spider: Spider) -> bool:
        """Overridden to add boolean condition on matching path regex"""
        # hostname can be None for wrong urls (like javascript links)
        cahched_request = urlparse_cached(request)
        host = cahched_request.hostname or ""

        return bool(self.host_regex.search(host) and self.host_path_regex.search(cahched_request.geturl()))

    def process_request(self, request: Request) -> None:
        """If the superclass process_request() raises an IgnoreRequest, log the error"""
        try:
            return super().process_request(request)
        except IgnoreRequest:
            if request.url in self.crawler.spider.start_urls:
                self.crawler.spider.logger.exception(
                    "IgnoreRequest raised for starting URL due to Offsite request: %s, allowed_domains: %s",
                    request.url,
                    self.crawler.spider.allowed_domains,
                )
            raise

    def get_host_path_regex(self, spider: Spider) -> re.Pattern:
        """New method, modified from 'get_host_regex' method to return path related regex"""
        allowed_domain_paths = getattr(spider, "allowed_domain_paths", None)
        if not allowed_domain_paths:
            return re.compile("")  # allow all by default
        url_pattern = re.compile(r"^https?://.*$")
        port_pattern = re.compile(r":\d+$")
        domains = []

        for domain in allowed_domain_paths:
            if domain is None:
                continue
            if url_pattern.match(domain):
                message = (
                    "allowed_domain_paths accepts only domains, not URLs. "
                    f"Ignoring URL entry {domain} in allowed_domain_paths."
                )
                warnings.warn(message)
            elif port_pattern.search(domain):
                message = (
                    "allowed_domain_paths accepts only domains without ports. "
                    f"Ignoring entry {domain} in allowed_domain_paths."
                )
                warnings.warn(message)
            else:
                domains.append(re.escape(domain))
        regex = rf"{'|'.join(domains)}"
        return re.compile(regex)
