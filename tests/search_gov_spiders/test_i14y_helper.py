from search_gov_crawler.elasticsearch.i14y_helper import (
    parse_date_safely,
    detect_lang,
    separate_file_name,
)


# Tests for parse_date_safely
def test_parse_date_safely_valid_date():
    assert parse_date_safely("2025-03-13") == "2025-03-13T00:00:00"


def test_for_known_date_issues():
    sampleDates = {
        "5/30/2024 7:24:49 AM": "2024-05-30T07:24:49",
        "Wed, 02 Nov 1998": "1998-11-02T00:00:00",
        "2025-03-14 00:00:00.0": "2025-03-14T00:00:00",
        "2024-04-08 18:17:47-04:00": "2024-04-08T18:17:47",
        "Thursday, August 10, 2023": "2023-08-10T00:00:00",
        "January 8, 2013 10:05:30 AM EST": "2013-01-08T10:05:30",
        "jibberish": None,
        "2025-02-16T04:18:11.491+00:00": "2025-02-16T04:18:11",
        "2024-02-22T00:00:00": "2024-02-22T00:00:00",
    }
    for date in sampleDates:
        assert parse_date_safely(date) == sampleDates[date]


def test_parse_date_safely_empty_string():
    assert parse_date_safely("") is None


def test_parse_date_safely_none():
    assert parse_date_safely(None) is None


def test_parse_date_safely_zero():
    assert parse_date_safely(0) is None


def test_parse_date_safely_false():
    assert parse_date_safely(False) is None


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
