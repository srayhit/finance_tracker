"""Tiny helpers shared by services and the UI."""

from __future__ import annotations

import re
import secrets
import time

_SAFE_TEXT = re.compile(r"\s+")


def new_id(prefix: str) -> str:
    """Short opaque ID, e.g. txn_m4k2p9x1ab."""
    return f"{prefix}_{int(time.time() * 1000):x}{secrets.token_hex(3)}"


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: object, max_len: int = 120) -> str:
    text = _SAFE_TEXT.sub(" ", str(value or "").strip())
    return text[:max_len]


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def as_int(value: object, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(round(float(str(value).replace(",", ""))))
    except (TypeError, ValueError):
        return default
