import pytest

from search_gov_crawler.dap.transform import domain_is_valid, transform_dap_response


def test_transform_dap_response():
    input_data = [
        {
            "id": 1,
            "date": "2025-05-21",
            "report_name": "site",
            "report_agency": None,
            "domain": "www.example.com",
            "visits": 100,
        },
        {
            "id": 2,
            "date": "2025-05-21",
            "report_name": "site",
            "report_agency": None,
            "domain": "example.com",
            "visits": 100,
        },
        {
            "id": 3,
            "date": "2025-05-21",
            "report_name": "site",
            "report_agency": None,
            "domain": "another-example.com",
            "visits": 100,
        },
    ]

    expected_output = [
        {
            "domain": "example.com",
            "visits": 200,
            "date": "2025-05-21",
        },
        {
            "domain": "another-example.com",
            "visits": 100,
            "date": "2025-05-21",
        },
    ]

    assert transform_dap_response(input_data) == expected_output


DOMAIN_IS_VALID_TEST_CASES = [
    ("example.com", True),
    ("another-example.com", True),
    ("subdomain.example.com", True),
    ("example.co.uk", True),
    ("(not set)", False),
    ("(other)", False),
    ("", False),
    ("12345", False),
    (".example.com", False),
    ("example.com.", False),
    ("examplecom", False),
]


@pytest.mark.parametrize(("domain, is_valid"), DOMAIN_IS_VALID_TEST_CASES)
def test_domain_is_valid(domain, is_valid):
    assert domain_is_valid(domain) is is_valid
