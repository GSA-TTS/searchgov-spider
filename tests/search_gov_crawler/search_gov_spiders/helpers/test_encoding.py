import pytest

from search_gov_crawler.search_gov_spiders.helpers.encoding import decode_http_response, detect_encoding


@pytest.mark.parametrize(("input_str", "encoding"), [(b"", None), (b"This is UTF-8", "ASCII")])
def test_detect_encoding(input_str, encoding):
    assert detect_encoding(input_str) == encoding


def test_detect_encoding_viscii(mocker):
    mock_detect = mocker.patch("cchardet.detect")
    mock_detect.return_value.get.return_value = "VISCII"
    assert detect_encoding("Đánh Tiếng Việt".encode()) == "cp1258"


def test_decode_http_response_utf8():
    response_bytes = b"This is a UTF-8 string"
    decoded_string = decode_http_response(response_bytes)
    assert decoded_string == "This is a UTF-8 string"


def test_decode_http_response_non_utf8():
    response_bytes = b"\xc2\xa0This is not UTF-8"  # Example non-UTF-8
    decoded_string = decode_http_response(response_bytes)
    # Check if it decodes with detected encoding or falls back to string representation
    assert (
        "This is not UTF-8" in decoded_string or repr(response_bytes) == decoded_string
    )  # Allows for either decode or fallback


def test_decode_http_response_empty():
    response_bytes = b""
    decoded_string = decode_http_response(response_bytes)
    assert decoded_string == ""


def test_decode_unicode_error_from_decode():
    response_bytes = b"\x80abc"
    decoded_string = decode_http_response(response_bytes)
    assert decoded_string == response_bytes.decode("WINDOWS-1252")


def test_decode_unicode_error_from_both_decodes(mocker):
    response_bytes = b"\x80abc"
    mock_detect = mocker.patch("cchardet.detect")
    mock_detect.return_value.get.return_value = "UTF-8"
    decoded_string = decode_http_response(response_bytes)
    assert decoded_string == str(response_bytes)
