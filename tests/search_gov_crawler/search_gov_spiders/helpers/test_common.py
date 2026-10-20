import pytest

from search_gov_crawler.search_gov_spiders.helpers.common import split_optional_str_or_sequence

SPLIT_OPTIONAL_STR_OR_SEQUENCE_TEST_CASES = [
    (None, ()),
    ("example.com", ("example.com",)),
    ("1.example.com,2.example.com", ("1.example.com", "2.example.com")),
    (("1.example.com", "2.example.com"), ("1.example.com", "2.example.com")),
    (["1.example.com", "2.example.com"], ("1.example.com", "2.example.com")),
]


@pytest.mark.parametrize(("input_argument", "expected_output"), SPLIT_OPTIONAL_STR_OR_SEQUENCE_TEST_CASES)
def test_split_optional_str_or_sequence(input_argument, expected_output):
    assert split_optional_str_or_sequence(input_argument) == expected_output
