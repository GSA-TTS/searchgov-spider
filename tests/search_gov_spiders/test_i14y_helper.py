import pytest
from nltk.corpus import stopwords

from search_gov_crawler.search_engines.i14y_helper import (
    detect_lang,
    parse_date_safely,
    separate_file_name,
    summarize_text,
    update_dap_visits_to_document,
)


# Tests for parse_date_safely
def test_parse_date_safely_valid_date():
    assert parse_date_safely("2025-03-13") == "2025-03-13T00:00:00"


PARSE_DATE_TEST_CASES = [
    ("5/30/2024 7:24:49 AM", "2024-05-30T07:24:49"),
    ("Wed, 02 Nov 1998", "1998-11-02T00:00:00"),
    ("2025-03-14 00:00:00.0", "2025-03-14T00:00:00"),
    ("2024-04-08 18:17:47-04:00", "2024-04-08T18:17:47"),
    ("Thursday, August 10, 2023", "2023-08-10T00:00:00"),
    ("January 8, 2013 10:05:30 AM EST", "2013-01-08T10:05:30"),
    ("jibberish", None),
    ("2025-02-16T04:18:11.491+00:00", "2025-02-16T04:18:11"),
    ("2024-02-22T00:00:00", "2024-02-22T00:00:00"),
    ("", None),
    (None, None),
    (0, None),
    (False, None),
]


@pytest.mark.parametrize(("input_str", "output_str"), PARSE_DATE_TEST_CASES)
def test_for_known_date_issues(input_str, output_str):
    assert parse_date_safely(input_str) == output_str


# Tests for detect_lang
def test_detect_lang_english():
    assert detect_lang("This is a test sentence in English. And, this is another test sentence in English.") == "en"


def test_detect_lang_spanish():
    assert detect_lang("Esta es una frase de prueba en español.") == "es"


def test_detect_lang_chinese():
    assert (
        detect_lang("这是一个中文测试句子。") == "zh"
        or detect_lang("这是一个中文测试句子.") == "zh"
        or detect_lang("这是一个中文测试句子.") == "zh"
    )


def test_detect_lang_short_text():
    assert detect_lang("How are you") == "en"


def test_detect_lang_empty_text():
    assert detect_lang("") is None


def test_detect_lang_unrecognizable_text():
    assert detect_lang("1234567890!@#$%^&*()") is None


# Tests for separate_file_name
def test_separate_file_name_camel_case():
    assert separate_file_name("camelCaseFile.pdf") == "camel Case File"


def test_separate_file_name_snake_case():
    assert separate_file_name("snake_case_file.pdf") == "snake case file"


def test_separate_file_name_kebab_case():
    assert separate_file_name("kebab-case-file.pdf") == "kebab case file"


def test_separate_file_name_pascal_case():
    assert separate_file_name("PascalCaseFile.pdf") == "Pascal Case File"


def test_separate_file_name_mixed_case():
    assert separate_file_name("mixedCase123File.pdf") == "mixed Case 123 File"


def test_separate_file_name_numbers():
    assert separate_file_name("file123Test.pdf") == "file 123 Test"


def test_separate_file_name_symbols():
    assert separate_file_name("file_with-symbols+test,file~name%test.pdf") == "file with symbols test file name test"


def test_separate_file_name_no_extension():
    assert separate_file_name("noExtensionFile") == "no Extension File"


def test_separate_file_name_multiple_dots():
    assert separate_file_name("file.with.multiple.dots.pdf") == "file with multiple dots"


def test_separate_file_name_empty():
    assert separate_file_name("") == ""


def test_separate_file_name_only_extension():
    assert separate_file_name(".pdf") == ""


SUMMARIZE_TEXT_TEST_CASES = [
    ("", "https://example.com", "en", None, None),
    (10, "https://example.com", "en", None, None),
    ("Hi there! I am testing this function", "https://example.com", None, None, None),
    (
        "Hi there! I am testing this function",
        "https://example.com",
        "en",
        "I am testing this function Hi there!",
        "hi, testing, function",
    ),
]


@pytest.mark.parametrize(("text", "url", "lang_code", "summary", "keyword"), SUMMARIZE_TEXT_TEST_CASES)
def test_summarize_text(text, url, lang_code, summary, keyword):
    assert summarize_text(text=text, url=url, lang_code=lang_code) == (summary, keyword)


def test_summarize_text_unsupported_stopwords(caplog):
    error_msg = (
        "Unsupported Language. Error when parsing https://example.com Missing "
        "Stopwords File: No such file or directory: "
    )

    with caplog.at_level("WARNING"):
        results = summarize_text("This is a test for missing stopwork", "https://example.com", "ko")

    assert results == (None, None)
    assert f"{error_msg}'{stopwords._root.path}/korean'" in caplog.messages


@pytest.mark.parametrize(
    ("input_doc", "domain_visits", "output_doc"),
    [
        ({"field1": "value1"}, None, {"field1": "value1"}),
        (
            {"field1": "value1", "domain_name": "example.com"},
            10,
            {"field1": "value1", "domain_name": "example.com", "dap_domain_visits_count": 10},
        ),
        (
            {"field1": "value1", "domain_name": "www.example.com"},
            10,
            {"field1": "value1", "domain_name": "www.example.com", "dap_domain_visits_count": 10},
        ),
        (
            {"field1": "value1", "domain_name": "missing.example.com"},
            None,
            {"field1": "value1", "domain_name": "missing.example.com"},
        ),
    ],
)
def test_update_dap_visits_to_document(input_doc, domain_visits, output_doc, mocker):
    spider = mocker.Mock()
    spider.domain_visits.get.return_value = domain_visits
    assert update_dap_visits_to_document(input_doc, spider) == output_doc
