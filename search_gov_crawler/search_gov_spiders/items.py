""" Define here the models for your scraped items
See documentation in:
https://docs.scrapy.org/en/latest/topics/items.html """

import scrapy


class SearchGovSpidersItem(scrapy.Item):
    """Class for Item which is a container for every returned scraped page"""
    response_bytes = scrapy.Field()
    url = scrapy.Field()
    output_target = scrapy.Field()
    response_language = scrapy.Field()
    content_type = scrapy.Field()
