import re
from typing import Optional

# Regex to remove unnecessary newlines unless preceded by punctuation or markup
NON_PUNCTUATION_NEWLINES = re.compile(r"(?<![p{P}>])\n", flags=re.UNICODE | re.MULTILINE)

def filter_printable_chars(char: str) -> str:
    """Return character if printable or a space, otherwise remove it."""
    return char if char.isprintable() or char.isspace() else ""

def remove_control_chars(text: str) -> str:
    """Remove non-printable and invalid XML characters from the text."""
    return "".join(map(filter_printable_chars, text))

def clean_line(line: str) -> Optional[str]:
    """Sanitize a line by removing HTML space entities, non-printable characters, and trimming spaces."""
    replacements = {"&#13;": "\r", "&#10;": "\n", "&nbsp;": "\u00A0"}
    for old, new in replacements.items():
        line = line.replace(old, new)
    
    sanitized_line = remove_control_chars(line)
    sanitized_line = trim_whitespace(NON_PUNCTUATION_NEWLINES.sub(" ", sanitized_line))
    return sanitized_line.strip() or ""

def sanitize_text(text: str) -> Optional[str]:
    """Sanitize an entire text block by processing each line while preserving or trimming spaces."""
    if not text:
        return None

    # Convert to string to remove non-printable characters and force string type
    text = clean_text = f"{text}"

    try:
        clean_text = "\n".join(
            filter(None, (clean_line(line) for line in text.splitlines()))
        ).replace("\u2424", "")
    except AttributeError:
        pass

    return replace_whitespace(clean_text)

def trim_whitespace(text: str) -> str:
    """Remove redundant spaces within the text string."""
    try:
        return " ".join(text.split()).strip()
    except (AttributeError, TypeError):
        return ""

def replace_whitespace(text: str) -> str:
    """Replaces all whitespace characters like \n, \t, \r, etc. with spaces."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()
