# ruff: noqa: T201
from search_gov_crawler.config.settings import SearchgovSettings
from search_gov_crawler.indexing.opensearch import SearchGovOpensearch
from search_gov_crawler.search_gov_spiders.items import FreshnessSpiderItem


def create_freshness_index(opensearch: SearchGovOpensearch, index_name: str):
    if not opensearch.index_exists(index_name=index_name):
        opensearch.create_index(template=FreshnessSpiderItem.generate_template(), index_name=index_name)
        print(f"Created index {index_name}")
    else:
        print(f"Index {index_name} already exists!")


if __name__ == "__main__":
    searchgov_settings = SearchgovSettings()
    opensearch = SearchGovOpensearch(searchgov_settings=searchgov_settings)
    create_freshness_index(opensearch=opensearch, index_name=searchgov_settings.opensearch_freshness_index)
