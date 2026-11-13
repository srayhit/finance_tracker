"""Never store account/card identifiers in free text or nicknames."""

from __future__ import annotations

import re

_LONG_DIGITS = re.compile(r"\b\d{10,19}\b")
_SPACED_DIGITS = re.compile(r"(?:\d[\s-]?){12,19}")
_CARD_PREFIX = re.compile(
    r"(?i)\b(?:card|a/c|account|acct)\s*(?:no\.?|number|#)\s*[:#-]?\s*"
)


def sanitize_free_text(value: object, max_len: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = _CARD_PREFIX.sub("", text)
    text = _LONG_DIGITS.sub("[redacted]", text)
    text = _SPACED_DIGITS.sub("[redacted] ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def validate_nickname(value: object) -> str:
    raw = str(value or "").strip()
    if _LONG_DIGITS.search(raw) or _SPACED_DIGITS.search(raw):
        raise ValueError("Nickname looks like an account/card number. Use a nickname only.")
    text = sanitize_free_text(raw, 60)
    if not text:
        raise ValueError("Nickname is required.")
    return text
