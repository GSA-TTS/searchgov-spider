import pytest
import requests

from search_gov_crawler.dap.connect import get_dap_api_configs, get_dap_page_by_date


@pytest.fixture(name="set_env_variables")
def fixture_set_env_variables(monkeypatch):
    monkeypatch.setenv("DAP_API_BASE_URL", "https://url-var.for.test")
    monkeypatch.setenv("DATA_GOV_API_KEY", "api-key-var-for-test")


@pytest.mark.usefixtures("set_env_variables")
def test_get_dap_api_configs():
    assert get_dap_api_configs() == ("https://url-var.for.test", "api-key-var-for-test")


@pytest.mark.usefixtures("set_env_variables")
@pytest.mark.parametrize("env_var", ["DAP_API_BASE_URL", "DATA_GOV_API_KEY"])
def test_get_dap_api_configs_missing(monkeypatch, env_var):
    monkeypatch.delenv(env_var, raising=False)
    with pytest.raises(ValueError, match=f"Missing environment variable value for {env_var}"):
        get_dap_api_configs()


@pytest.mark.usefixtures("set_env_variables")
def test_get_dap_page_by_date(mocker):
    mock_response = mocker.patch("requests.get")
    mock_response.return_value.json.return_value = {"this is": "the response"}

    get_dap_page_by_date("2025-05-21", 1000, 1)

    mock_response.assert_called_once_with(
        "https://url-var.for.test/reports/site/data?after=2025-05-21&before=2025-05-21&limit=1000&page=1",
        headers={"x-api-key": "api-key-var-for-test", "Accept": "application/json"},
        timeout=30,
    )


@pytest.mark.usefixtures("set_env_variables")
def test_get_dap_age_by_date_error(mocker, caplog):
    mock_response = mocker.patch("requests.get")
    mock_response.return_value.raise_for_status.side_effect = [requests.exceptions.HTTPError("Error")]

    with caplog.at_level("ERROR"):
        with pytest.raises(requests.exceptions.HTTPError):
            get_dap_page_by_date("2025-05-21", 1000, 1)

        assert any(message.startswith("Error during DAP request:") for message in caplog.messages)
