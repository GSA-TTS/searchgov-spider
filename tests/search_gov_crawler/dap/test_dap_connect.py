import pytest
import requests

from search_gov_crawler.dap.connect import get_dap_api_configs, get_dap_data_by_date


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
def test_get_dap_data_by_date(mocker):
    mock_session = mocker.patch("requests.Session")
    mock_session.get.return_value.json.side_effect = [
        [{"data": "data"}, {"data": "data"}],
        [{"data": "data"}, {"data": "data"}],
        [],
    ]

    dap_data = get_dap_data_by_date(mock_session, "https://url-var.for.test", "2025-05-21")
    assert dap_data == [{"data": "data"}, {"data": "data"}, {"data": "data"}, {"data": "data"}]


@pytest.mark.usefixtures("set_env_variables")
def test_get_dap_age_by_date_error(mocker, caplog):
    mock_session = mocker.patch("requests.Session")
    mock_session.get.return_value.raise_for_status.side_effect = [requests.exceptions.HTTPError("Error")]

    with caplog.at_level("ERROR"):
        with pytest.raises(requests.exceptions.HTTPError):
            get_dap_data_by_date(mock_session, "https://url-var.for.test", "2025-05-21")

        assert any(message.startswith("Error during DAP request:") for message in caplog.messages)
