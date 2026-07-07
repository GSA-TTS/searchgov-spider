import pytest
from nltk.corpus import stopwords

from search_gov_crawler.indexing.helpers import (
    detect_lang,
    get_base_extension,
    get_title_from_filename,
    parse_dates_safely,
    separate_filename,
    summarize_text,
    update_dap_visits_to_document,
)


# Tests for parse_dates_safely
def test_parse_date_safely_valid_date():
    assert parse_dates_safely("2025-03-13") == "2025-03-13T00:00:00"


PARSE_DATE_TEST_CASES = [
    (("5/30/2024 7:24:49 AM",), "2024-05-30T07:24:49"),
    (("not a date", "Wed, 02 Nov 1998"), "1998-11-02T00:00:00"),
    (("HI there!!", "2025-03-14 00:00:00.0"), "2025-03-14T00:00:00"),
    (("2024-04-08 18:17:47-04:00", "Thursday, August 10, 2023"), "2024-04-08T18:17:47"),
    (("Yes", "No", 0, "Thursday, August 10, 2023"), "2023-08-10T00:00:00"),
    (("January 8, 2013 10:05:30 AM EST",), "2013-01-08T10:05:30"),
    (("jibberish", "jibberish"), None),
    (("2025-02-16T04:18:11.491+00:00",), "2025-02-16T04:18:11"),
    (("2024-02-22T00:00:00",), "2024-02-22T00:00:00"),
    (("",), None),
    ((None,), None),
    ((0,), None),
    ((False,), None),
    ((None, 0, False), None),
]


@pytest.mark.parametrize(("input_strs", "output_str"), PARSE_DATE_TEST_CASES)
def test_for_known_date_issues(input_strs, output_str):
    assert parse_dates_safely(*input_strs) == output_str


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


SEPARATE_FILENAME_TEST_CASES = [
    ("camelCaseFile.pdf", "camel Case File"),
    ("snake_case_file.pdf", "snake case file"),
    ("kebab-case-file.pdf", "kebab case file"),
    ("PascalCaseFile.pdf", "Pascal Case File"),
    ("mixedCase123File.pdf", "mixed Case 123 File"),
    ("file123Test.pdf", "file 123 Test"),
    ("file_with-symbols+test,file~name%test.pdf", "file with symbols test file name test"),
    ("noExtensionFile", "no Extension File"),
    ("file.with.multiple.dots.pdf", "file with multiple dots"),
    ("sometimes%20a%20filename+is+encoded.pdf", "sometimes a filename is encoded"),
    ("", ""),
    (".pdf", ""),
    (
        "Something_Here_Triggers%20An%20ExtraSpace%20123456You know what I mean?.pdf",
        "Something Here Triggers An Extra Space 123456 You know what I mean?",
    ),
]


@pytest.mark.parametrize(("filename", "expected_output"), SEPARATE_FILENAME_TEST_CASES)
def test_separate_filename(filename, expected_output):
    assert separate_filename(filename) == expected_output


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
    (
        "Hi there! I am testing this function.  Hi again!",
        "https://example.com",
        "en",
        "I am testing this function. Hi again! Hi there!",
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


GET_BASE_EXTENSION_TEST_CASES = [
    ("https://www.example.com/", ("", "", "")),
    ("https://www.example.com/file.pdf", ("file", "pdf", "file.pdf")),
    ("https://www.example.com/path/", ("", "", "")),
    ("https://www.example.com/path", ("path", "", "path")),
    ("https://www.example.com/file.", ("file", "", "file")),
    ("https://www.example.com/path/one/two/file.pdf", ("file", "pdf", "file.pdf")),
    ("https://www.example.com/path/one/two/this is a file.pdf", ("this is a file", "pdf", "this is a file.pdf")),
    (
        "https://www.example.com/path/one/two/this%20is%20a%20file.pdf",
        ("this%20is%20a%20file", "pdf", "this%20is%20a%20file.pdf"),
    ),
    ("https://www.example.com/path/one/two/file.pdf?version=123", ("file", "pdf", "file.pdf")),
]


@pytest.mark.parametrize(("url", "expected_output"), GET_BASE_EXTENSION_TEST_CASES)
def test_get_base_extension(monkeypatch, url, expected_output):

    monkeypatch.setattr("search_gov_crawler.indexing.helpers.ensure_http_prefix", lambda x: x)
    assert get_base_extension(url) == expected_output


GET_TITLE_FROM_FILENAME_TEST_CASES = [
    ("file", "file"),
    ("file.pdf", "file"),
    ("another_file.pdf", "another_file"),
    ("ANOTHER_FILE.PDF", "ANOTHER_FILE"),
    ("One-More-File.pdf", "One-More-File"),
    ("and%20another%20one.pdf", "and another one"),
    ("why-not-one-more.pdf?version=T2000", "why-not-one-more"),
]


@pytest.mark.parametrize(("filename", "expected_title"), GET_TITLE_FROM_FILENAME_TEST_CASES)
def test_get_title_from_filename(filename, expected_title):
    assert get_title_from_filename(filename) == expected_title
