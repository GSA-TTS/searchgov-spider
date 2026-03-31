import pytest
from scrapy.utils.project import get_project_settings


@pytest.fixture(name="project_settings")
def fixture_project_settings(monkeypatch):
    monkeypatch.setenv("SCRAPY_SETTINGS_MODULE", "search_gov_crawler.search_gov_spiders.settings")
    return get_project_settings()
