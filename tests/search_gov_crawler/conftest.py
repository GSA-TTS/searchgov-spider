import os

import pytest
from scrapy.utils.project import get_project_settings

from search_gov_crawler.config.settings import SearchgovSettings


@pytest.fixture
def project_settings(monkeypatch):
    monkeypatch.setenv("SCRAPY_SETTINGS_MODULE", "search_gov_crawler.search_gov_spiders.settings.common")
    return get_project_settings()


@pytest.fixture
def domain_spider_settings(project_settings):
    project_settings.setmodule("search_gov_crawler.search_gov_spiders.settings.domain_spider")
    return project_settings


@pytest.fixture
def default_searchgov_settings(mocker, monkeypatch):
    mocker.patch.dict(os.environ, clear=True)
    monkeypatch.setitem(SearchgovSettings.model_config, "env_file", "")
    return SearchgovSettings()
