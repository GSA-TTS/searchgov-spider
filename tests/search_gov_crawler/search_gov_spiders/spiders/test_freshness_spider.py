from search_gov_crawler.search_gov_spiders.spiders.freshness_spider import FreshnessSpider


def test_freshness_spider_args(mocker):
    mocker.patch("search_gov_crawler.search_gov_spiders.spiders.freshness_spider.SearchGovOpensearch")
    spider = FreshnessSpider(query='{"test": "query"}', max_results="100")

    assert spider.query == {"test": "query"}
    assert spider.max_results == 100
