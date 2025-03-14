from search_gov_crawler.elasticsearch.i14y_helper import null_date, detect_lang, separate_file_name

# Tests for null_date
def test_null_date_valid_date():
    assert null_date("2025-03-13") == "2025-03-13"

def test_null_date_empty_string():
    assert null_date("") is None

def test_null_date_none():
    assert null_date(None) is None

def test_null_date_zero():
    assert null_date(0) is None

def test_null_date_false():
    assert null_date(False) is None

# Tests for detect_lang
def test_detect_lang_english():
    assert detect_lang("This is a test sentence in English. And, this is another test sentence in English.") == "en"

def test_detect_lang_spanish():
    assert detect_lang("Esta es una frase de prueba en español.") == "es"

def test_detect_lang_chinese():
    assert detect_lang("这是一个中文测试句子。") == "zh" or detect_lang("这是一个中文测试句子.") == "zh" or detect_lang("这是一个中文测试句子.") == "zh"

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
