"""Define here the models for your scraped items
See documentation in:
https://docs.scrapy.org/en/latest/topics/items.html"""

import scrapy


class SearchGovSpidersItem(scrapy.Item):
    """Class for Item which is a container for every returned scraped page"""

    response_bytes = scrapy.Field()
    url = scrapy.Field()
    output_target = scrapy.Field()
    response_language = scrapy.Field()
    content_type = scrapy.Field()

    def __repr__(self) -> str:
        """Override the default __repr__ so that we don't print the response_bytes which is very long sometimes."""

        return (
            f"Item(url={self.get('url')}, output_target={self.get('output_target')}, "
            f"content_type={self.get('content_type')}, response_language={self.get('response_language')})"
        )
