import logging

import cchardet  # Faster and more reliable character encoding detection than chardet

# Needs muting to avoid its debug mode
logging.getLogger("cchardet").setLevel("INFO")


def detect_encoding(data: bytes) -> str | None:
    """Detect the encoding of the given byte string."""
    detection_result = cchardet.detect(data)
    encoding = detection_result.get("encoding")

    # VISCII is not fully supported by python but can use cp1258
    if str(encoding).upper() == "VISCII":
        return "cp1258"

    return encoding or None


def decode_http_response(response_bytes: bytes) -> str:
    """Decode an HTTP response, using the detected encoding or the response's default encoding."""
    try:
        decoded_response = response_bytes.decode("utf-8")
    except UnicodeDecodeError:
        detected_encoding = detect_encoding(response_bytes)

        try:
            decoded_response = response_bytes.decode(detected_encoding)
        except (UnicodeDecodeError, TypeError):
            decoded_response = str(response_bytes)

    return decoded_response
