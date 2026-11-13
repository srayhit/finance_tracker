"""Load the seed lexicon. No network access at runtime."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

LEXICON_PATH = Path(__file__).with_name("lexicon.yaml")


@lru_cache(maxsize=1)
def load_lexicon() -> dict:
    with LEXICON_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def tag_id(tag_type: str, key: str) -> str:
    return f"tag_{tag_type}_{key}"


def iter_seed_tags():
    """Yield typed tag dictionaries for seeding the Tags tab."""
    data = load_lexicon()

    for key, entry in (data.get("channels") or {}).items():
        yield {
            "TagID": tag_id("channel", key),
            "Name": key,
            "Type": "channel",
            "Aliases": ", ".join([key, *(entry.get("aliases") or [])]),
            "ParentTag": "",
            "DefaultCategoryID": "",
        }

    for key, entry in (data.get("methods") or {}).items():
        yield {
            "TagID": tag_id("method", key),
            "Name": key,
            "Type": "method",
            "Aliases": ", ".join([key, *(entry.get("aliases") or [])]),
            "ParentTag": "",
            "DefaultCategoryID": "",
        }

    for key, entry in (data.get("services") or {}).items():
        yield {
            "TagID": tag_id("service", key),
            "Name": key,
            "Type": "service",
            "Aliases": ", ".join(
                [key, entry.get("display_name", key), *(entry.get("aliases") or [])]
            ),
            "ParentTag": "",
            "DefaultCategoryName": entry.get("category", ""),
        }

    for key, entry in (data.get("merchants") or {}).items():
        yield {
            "TagID": tag_id("merchant", key),
            "Name": key,
            "Type": "merchant",
            "Aliases": ", ".join(
                [key, entry.get("display_name", key), *(entry.get("aliases") or [])]
            ),
            "ParentTag": "",
            "DefaultCategoryName": entry.get("default_category", ""),
        }

    for key, entry in (data.get("items") or {}).items():
        yield {
            "TagID": tag_id("item", key),
            "Name": key,
            "Type": "item",
            "Aliases": ", ".join(
                [key, entry.get("display_name", key), *(entry.get("aliases") or [])]
            ),
            "ParentTag": tag_id("item", entry["parent"]) if entry.get("parent") else "",
            "DefaultCategoryName": entry.get("category", ""),
        }


def service_meta() -> dict:
    return load_lexicon().get("services") or {}


def merchant_meta() -> dict:
    return load_lexicon().get("merchants") or {}
