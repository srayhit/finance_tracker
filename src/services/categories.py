"""Category helpers. Categories are global reference data, not per-user."""

from __future__ import annotations

import re

from src.db.repo import append_rows, read_tab, update_row
from src.db.schemas import DEFAULT_CATEGORIES
from src.utils.ids import clean_text

CATEGORY_TYPES = ["Expenditure", "Income", "Investment"]


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return text or "other"


def category_id(category_type: str, name: str) -> str:
    return f"cat_{slugify(category_type)}_{slugify(name)}"


def default_category_rows() -> list[dict]:
    rows = []
    for category_type in CATEGORY_TYPES:
        for name in DEFAULT_CATEGORIES[category_type]:
            rows.append(
                {
                    "CategoryID": category_id(category_type, name),
                    "Type": category_type,
                    "Category": name,
                    "ParentCategory": "",
                    "IsActive": "TRUE",
                }
            )
    return rows


def list_categories(category_type: str | None = None, active_only: bool = True):
    df = read_tab("Categories")
    if df.empty:
        return []
    rows = df.to_dict("records")
    if category_type:
        wanted = category_type.strip().lower()
        rows = [r for r in rows if str(r.get("Type", "")).strip().lower() == wanted]
    if active_only:
        rows = [
            r
            for r in rows
            if str(r.get("IsActive", "TRUE")).strip().lower() not in {"false", "0", "no"}
        ]
    return rows


def category_map() -> dict[str, dict]:
    return {str(row.get("CategoryID")): row for row in list_categories(active_only=False)}


def get_category(category_id_value: str) -> dict | None:
    return category_map().get(str(category_id_value))


def find_category_by_name(name: str, category_type: str | None = None) -> dict | None:
    target = clean_text(name).lower()
    if not target:
        return None
    candidates = list_categories(category_type=category_type, active_only=False)
    for row in candidates:
        if str(row.get("Category", "")).strip().lower() == target:
            return row
    for row in candidates:
        if target in str(row.get("Category", "")).strip().lower():
            return row
    return None


def ensure_category(name: str, category_type: str) -> dict:
    clean_name = clean_text(name, 60)
    if not clean_name:
        raise ValueError("Category name is required.")
    if category_type not in CATEGORY_TYPES:
        raise ValueError(f"Unknown category type: {category_type}")
    existing = find_category_by_name(clean_name, category_type)
    if existing:
        return existing
    row = {
        "CategoryID": category_id(category_type, clean_name),
        "Type": category_type,
        "Category": clean_name,
        "ParentCategory": "",
        "IsActive": "TRUE",
    }
    append_rows("Categories", [row])
    return row


def ensure_category_rows(rows: list[dict]) -> None:
    """Seed categories once, preserving any custom categories already present."""
    existing = list_categories(active_only=False)
    seen = {
        (str(r.get("Type", "")).strip().lower(), str(r.get("Category", "")).strip().lower())
        for r in existing
    }
    new_rows = []
    for row in rows:
        key = (
            str(row.get("Type", "")).strip().lower(),
            str(row.get("Category", "")).strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        new_rows.append(row)
    if new_rows:
        append_rows("Categories", new_rows)


def set_category_active(category_id_value: str, active: bool) -> bool:
    row = get_category(category_id_value)
    if not row:
        return False
    row["IsActive"] = "TRUE" if active else "FALSE"
    return update_row("Categories", "CategoryID", category_id_value, row)
