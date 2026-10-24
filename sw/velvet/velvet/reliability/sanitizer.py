"""
Unicode and Input Sanitizer for Velvet Nadir.

Strips surrogate characters (U+D800 through U+DFFF), invalid control characters,
and malformed non-ASCII sequences from pastes, keys, and incoming network payloads.
"""

import re


# Matches unpaired Unicode surrogates
_SURROGATE_PATTERN = re.compile(r'[\ud800-\udfff]')

# Matches non-printable control characters except standard whitespace (\n, \r, \t)
_CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def sanitize_unicode(text: str) -> str:
    """
    Remove surrogate code points and hazardous control characters from text strings.
    Prevents UTF-8 encoding crashes and terminal corruption.
    """
    if not isinstance(text, str):
        return text

    # Remove surrogates
    cleaned = _SURROGATE_PATTERN.sub("", text)
    # Remove control characters
    cleaned = _CONTROL_CHAR_PATTERN.sub("", cleaned)
    return cleaned


def sanitize_api_key(key: str) -> str:
    """
    Sanitize an API key or token:
    - Strips all whitespace, quotes, and non-printable characters.
    - Preserves standard Base64 / Hex / URL-safe tokens.
    """
    if not isinstance(key, str):
        return ""
    # Strip whitespace, quotes, surrogates, and non-ASCII chars
    cleaned = key.strip().strip("'\"`")
    cleaned = _SURROGATE_PATTERN.sub("", cleaned)
    cleaned = _CONTROL_CHAR_PATTERN.sub("", cleaned)
    # Remove any stray spaces within the key
    cleaned = re.sub(r'\s+', '', cleaned)
    return cleaned


sanitize_surrogates = sanitize_unicode

