from search_gov_crawler.search_gov_spiders.helpers.content import sanitize_text

def test_sanitize_text_empty_string():
    assert sanitize_text("") is None

def test_sanitize_text_none():
    assert sanitize_text(None) is None

def test_sanitize_text_basic():
    text = "This is a test string."
    assert sanitize_text(text) == "This is a test string."

def test_sanitize_text_with_html_entities():
    text = "This is a test with &nbsp; non-breaking space and &#10; newline and &#13; carriage return."
    assert sanitize_text(text) == "This is a test with non-breaking space and newline and carriage return."

def test_sanitize_text_with_control_characters():
    text = "This is a test with \x01 control character."  # \x01 is a non-printable character
    assert sanitize_text(text) == "This is a test with control character."

def test_sanitize_text_with_newlines():
    text = "This is line 1.\nThis is line 2.\nThis is line 3."
    assert sanitize_text(text) == "This is line 1. This is line 2. This is line 3."

def test_sanitize_text_with_newlines_and_punctuation():
    text = "This is line 1.\nThis is line 2.\n>This is line 3.\nThis is line 4"
    assert sanitize_text(text) == "This is line 1. This is line 2. >This is line 3. This is line 4"

def test_sanitize_text_with_multiple_spaces():
    text = "This is a test   with   multiple    spaces."
    assert sanitize_text(text) == "This is a test with multiple spaces."

def test_sanitize_text_with_leading_and_trailing_spaces():
    text = "   This is a test with leading and trailing spaces.   "
    assert sanitize_text(text) == "This is a test with leading and trailing spaces."

def test_sanitize_text_with_empty_lines():
    text = "Line 1\n\nLine 3"
    assert sanitize_text(text) == "Line 1 Line 3"

def test_sanitize_text_with_unicode_character():
    text = "This is a test with a Unicode character: \u2424." # Symbol for blank
    assert sanitize_text(text) == "This is a test with a Unicode character: ."

def test_sanitize_text_with_mixed_whitespace():
    text = "This is a test.\n\t  With \r\n mixed \f\v whitespace.  "
    assert sanitize_text(text) == "This is a test. With mixed whitespace."

def test_sanitize_text_with_only_whitespace_lines():
    text = "   \n\t\r\n   "
    assert sanitize_text(text) == ""

def test_sanitize_text_with_punctuation_and_newlines():
    text = "Test sentence.\nAnother sentence!\n\"Quoted sentence.\"\n(Parenthetical sentence).\n[Bracketed sentence].\n{Braced sentence}.\n<Angle bracketed sentence>.\n'Apostrophe sentence'."
    expected = "Test sentence. Another sentence! \"Quoted sentence.\" (Parenthetical sentence). [Bracketed sentence]. {Braced sentence}. <Angle bracketed sentence>. 'Apostrophe sentence'."
    assert sanitize_text(text) == expected
