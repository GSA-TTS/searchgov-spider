import hashlib
import logging
import os
import re
from datetime import UTC, datetime
from urllib.parse import urlparse
from dotenv import load_dotenv
from dateutil import parser
from langdetect import detect
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from search_gov_crawler.search_gov_spiders.extensions.json_logging import LOG_FMT
from pythonjsonlogger.json import JsonFormatter
from typing import Any
from dateutil.parser import ParserError

# fmt: off
ALLOWED_LANGUAGE_CODE = {
    "ar": "arabic", "bg": "bulgarian", "bn": "bengali", "ca": "catalan", "cs": "czech", "da": "danish",
    "de": "german", "el": "greek", "en": "english", "es": "spanish", "et": "estonian", "fa": "persian", "fr": "french",
    "he": "hebrew", "hi": "hindi", "hr": "croatian", "ht": "haitian creole", "hu": "hungarian", "hy": "armenian", "id": "indonesian",
    "it": "italian", "ja": "japanese", "km": "khmer", "ko": "korean", "lt": "lithuanian", "lv": "latvian", "mk": "macedonian",
    "nl": "dutch", "pl": "polish", "ps": "pashto", "pt": "portuguese", "ro": "romanian", "ru": "russian", "sk": "slovak", "so": "somali",
    "sq": "albanian", "sr": "serbian", "sw": "swahili", "th": "thai", "tr": "turkish", "uk": "ukrainian", "ur": "urdu", "uz": "uzbek",
    "vi": "vietnamese", "zh": "chinese",
}
# fmt: on

load_dotenv()
logging.basicConfig(level=os.environ.get("SCRAPY_LOG_LEVEL", "INFO"))
logging.getLogger().handlers[0].setFormatter(JsonFormatter(fmt=LOG_FMT))
logger = logging.getLogger("search_gov_crawler.i14y_helper")


def parse_date_safely(date_value: Any) -> str | None:
    """
    Convert falsey date values (like an empty string) to None,
    which will yield a null value in elasticsearch.

    Args:
        date_value (str | Any): Date value that needs to fallback to null

    Returns:
        str: Either the date in isoformat (YYYY-MM-DD'T'HH:MM:SS), or None
    """
    datetime_format = "%Y-%m-%dT%H:%M:%S"

    if date_value is None or date_value == "":
        return None

    if isinstance(date_value, datetime):
        return date_value.strftime(datetime_format)

    try:
        datetime_object = parser.parse(date_value, fuzzy=True)
        return datetime_object.strftime(datetime_format)

    except (ParserError, TypeError):
        logger.warning("Could not parse date: '%s'", date_value)
        return None


def detect_lang(text: str) -> str:
    """
    Detect language based on charachters and encoding

    Args:
        text (str): The text with the language in question

    Returns:
        str: A two letter language code, eg: "en", "es", "zh", ...
    """
    try:
        lang = detect(text[:64])
        return lang[:2] if len(lang) > 1 else None
    except Exception:
        pass
    return None


def summarize_text(text: str, lang_code: str = None):
    """
    Summarizes text and extracts keywords using nltk, and calculates execution time.

    Args:
        text (str): extracted text/content

    Returns:
        tuple: (summary, keywords)
    """

    if (lang_code not in ALLOWED_LANGUAGE_CODE) or not text or type(text) != str:
        return None, None
    stop_words = set(stopwords.words(ALLOWED_LANGUAGE_CODE[lang_code]))
    sentences = sent_tokenize(text)

    word_frequencies = {}
    sentence_scores = {}

    for sentence in sentences:
        for word in word_tokenize(sentence.lower()):
            if word.isalnum() and word not in stop_words:
                if word not in word_frequencies:
                    word_frequencies[word] = 1
                else:
                    word_frequencies[word] += 1

            if word in word_frequencies:
                if sentence not in sentence_scores:
                    sentence_scores[sentence] = word_frequencies[word]
                else:
                    sentence_scores[sentence] += word_frequencies[word]

    summary_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:3]
    summary = " ".join(summary_sentences)

    sorted_words = sorted(word_frequencies, key=word_frequencies.get, reverse=True)[:10]
    keywords = ", ".join(sorted_words)

    return summary, keywords


def separate_file_name(file_name):
    """
    Separates a file name into words, maintaining capitalization.
    """
    base_name = file_name.rsplit(".", 1)[0].replace(".", " ")
    words = re.split(r"(?<!^)(?=[A-Z][a-z])|(?<=[a-z])(?=[A-Z])|[-_+~,%]|(?<=\D)(?=\d)|(?<=\d)(?=\D)", base_name)
    return " ".join(words)


def ensure_http_prefix(url: str):
    """Add http prefix if missing."""
    return url if url.startswith(("http://", "https://")) else f"https://{url}"


def get_url_path(url: str) -> str:
    """Extracts the path from a URL."""
    url = ensure_http_prefix(url)
    return urlparse(url).path


def get_base_extension(url: str) -> tuple[str, str]:
    """Extracts the basename and file extension from a URL."""
    url = ensure_http_prefix(url)
    basename, extension = os.path.splitext(os.path.basename(urlparse(url).path))
    if extension.startswith("."):
        extension = extension[1:]
    return basename, extension


def current_utc_iso() -> str:
    """Returns the current UTC timestamp in ISO format."""
    return datetime.now(tz=UTC).isoformat(timespec="milliseconds") + "Z"


def generate_url_sha256(url: str) -> str:
    """Generates a SHA-256 hash for a given URL."""
    url = ensure_http_prefix(url)
    return hashlib.sha256(url.encode()).hexdigest()


def get_domain_name(url: str) -> str:
    """Extracts the domain from a URL, support www (only if the url was parsed with it) ensuring consistency."""
    url = ensure_http_prefix(url)
    parsed = urlparse(url)
    return parsed.netloc
