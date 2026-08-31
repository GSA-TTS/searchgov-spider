def test_searchgov_settings_defaults(default_searchgov_settings):
    assert default_searchgov_settings.model_dump() == {
        "scrapy_log_level": "INFO",
        "opensearch_search_host": "http://localhost:9200",
        "opensearch_search_user": "",
        "opensearch_search_password": "",
        "opensearch_search_index": "spider-searchgov",
        "opensearch_freshness_index": "spider-freshness",
        "dap_extractor_schedule": "",
        "dap_visits_days_back": 7,
        "dap_visits_max_age": 28,
        "dlm_schedule": "45 * * * *",
        "dlm_max_docs": 500,
    }
