"""Idempotent one-time setup and v1 -> v2 migration.

Rules:
- back up every legacy tab to ``_v1_<name>`` before touching it;
- never overwrite a v2 tab that already has data rows;
- never delete legacy ``Transactions`` or ``Investments``;
- write seeds in batches to stay well inside the Sheets write quota.
"""

from __future__ import annotations

import json
from datetime import date

import streamlit as st

from src.data.lexicon import iter_seed_tags, load_lexicon
from src.db.repo import (
    append_rows,
    clear_cache,
    ensure_all_tabs,
    read_values,
    set_meta,
    worksheet_exists,
    write_raw,
    write_tab,
)
from src.db.schemas import (
    APP_VERSION,
    DEFAULT_SETTINGS,
    SCHEMA_VERSION,
    V2_SCHEMAS,
)
from src.services.categories import (
    category_id,
    default_category_rows,
    ensure_category_rows,
    find_category_by_name,
)
from src.utils.ids import as_int, clean_text, new_id, now_iso

LEGACY_TABS = ["Transactions", "Investments", "Accounts", "Categories", "CreditCards"]
BACKUP_PREFIX = "_v1_"

LEGACY_KIND_MAP = {
    "savings": "savings",
    "salary": "savings",
    "current": "current",
    "upi": "wallet",
    "upi / wallet": "wallet",
    "wallet": "wallet",
    "cash": "cash",
    "brokerage": "brokerage",
    "credit card": "credit_card",
    "card": "credit_card",
    "loan": "loan",
}


def _rows_from_values(values: list[list[str]]) -> tuple[list[str], list[dict]]:
    if not values:
        return [], []
    header = [str(cell).strip() for cell in values[0]]
    rows: list[dict] = []
    for raw in values[1:]:
        cells = [str(cell).strip() for cell in raw]
        if not any(cells):
            continue
        if cells == header:
            continue
        padded = cells + [""] * (len(header) - len(cells))
        record = dict(zip(header, padded))
        if not any(str(value).strip() for key, value in record.items() if key not in {"Timestamp"}):
            continue
        rows.append(record)
    return header, rows


def _v2_has_data(tab: str) -> bool:
    values = read_values(tab)
    if not values or len(values) < 2:
        return False
    header = [str(cell).strip() for cell in values[0]]
    id_column = V2_SCHEMAS.get(tab, [""])[0]
    if id_column not in header:
        return False
    index = header.index(id_column)
    for row in values[1:]:
        if len(row) > index and str(row[index]).strip():
            return True
    return False


def _backup_tab(name: str, summary: dict) -> None:
    if not worksheet_exists(name):
        return
    backup = f"{BACKUP_PREFIX}{name}"
    if worksheet_exists(backup):
        summary["backups_skipped"].append(name)
        return
    values = read_values(name)
    if not values:
        return
    write_raw(backup, values)
    summary["backups"].append(backup)


def _parse_day(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return ""
    try:
        day = int(digits[:2] if len(digits) > 2 else digits)
    except ValueError:
        return ""
    return str(day) if 1 <= day <= 31 else ""


def _legacy_account_rows(summary: dict, owner: str) -> list[dict]:
    # One owner per spreadsheet: migrated rows belong to this sheet's alias,
    # otherwise they would be invisible to every query in the app.
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(row: dict) -> None:
        key = (row["User"].lower(), row["Nickname"].lower())
        if key in seen:
            row["Nickname"] = f"{row['Nickname']} ({row['Kind'].replace('_', ' ')})"
            key = (row["User"].lower(), row["Nickname"].lower())
        if key in seen:
            row["Nickname"] = f"{row['Nickname']} {len(rows) + 1}"
        seen.add(key)
        rows.append(row)

    values = read_values(f"{BACKUP_PREFIX}Accounts")
    _, legacy_accounts = _rows_from_values(values)
    for record in legacy_accounts:
        user = owner
        nickname = clean_text(record.get("AccountName"), 60)
        if not nickname:
            continue
        raw_kind = clean_text(record.get("AccountType"), 40).lower()
        kind = LEGACY_KIND_MAP.get(raw_kind, "savings")
        opened = str(record.get("Timestamp", ""))[:10] or date.today().isoformat()
        add(
            {
                "AccountID": new_id("acc"),
                "Timestamp": now_iso(),
                "User": user,
                "Nickname": nickname,
                "Kind": kind,
                "Institution": clean_text(record.get("BankName"), 80),
                "Currency": "INR",
                "OpeningBalance": 0,
                "OpeningDate": opened,
                "CreditLimit": 0,
                "StatementDay": "",
                "DueDay": "",
                "IsActive": "TRUE",
                "Notes": "Migrated from v1",
            }
        )

    values = read_values(f"{BACKUP_PREFIX}CreditCards")
    _, legacy_cards = _rows_from_values(values)
    for record in legacy_cards:
        user = owner
        nickname = clean_text(record.get("CardName"), 60)
        if not nickname:
            continue
        add(
            {
                "AccountID": new_id("acc"),
                "Timestamp": now_iso(),
                "User": user,
                "Nickname": nickname,
                "Kind": "credit_card",
                "Institution": clean_text(record.get("BankName"), 80),
                "Currency": "INR",
                "OpeningBalance": 0,
                "OpeningDate": date.today().isoformat(),
                "CreditLimit": as_int(record.get("CreditLimit")) * 100,
                "StatementDay": "",
                "DueDay": _parse_day(record.get("DueDate")),
                "IsActive": "TRUE",
                "Notes": "Migrated from v1",
            }
        )

    summary["migrated_accounts"] = len(rows)
    return rows


def _migrate_accounts(summary: dict, owner: str) -> None:
    if _v2_has_data("Accounts"):
        summary["accounts"] = "kept existing v2 rows"
        return
    rows = _legacy_account_rows(summary, owner)
    write_tab("Accounts", rows)
    summary["accounts"] = f"wrote {len(rows)} migrated rows"


def _migrate_categories(summary: dict) -> None:
    if _v2_has_data("Categories"):
        ensure_category_rows(default_category_rows())
        summary["categories"] = "kept existing v2 rows; seeds ensured"
        return

    rows = default_category_rows()
    seen = {
        (str(r["Type"]).strip().lower(), str(r["Category"]).strip().lower()) for r in rows
    }
    values = read_values(f"{BACKUP_PREFIX}Categories")
    _, legacy_categories = _rows_from_values(values)
    added = 0
    for record in legacy_categories:
        raw_type = clean_text(record.get("Type"), 30)
        name = clean_text(record.get("Category"), 60)
        if not raw_type or not name:
            continue
        type_map = {
            "expenditure": "Expenditure",
            "expense": "Expenditure",
            "income": "Income",
            "investment": "Investment",
        }
        category_type = type_map.get(raw_type.lower())
        if not category_type:
            continue
        key = (category_type.lower(), name.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "CategoryID": category_id(category_type, name),
                "Type": category_type,
                "Category": name,
                "ParentCategory": "",
                "IsActive": "TRUE",
            }
        )
        added += 1
    write_tab("Categories", rows)
    summary["categories"] = f"wrote {len(rows)} categories ({added} legacy)"


def _seed_tags(summary: dict) -> None:
    existing = read_values("Tags")
    existing_ids: set[str] = set()
    if existing:
        header, rows = _rows_from_values(existing)
        if "TagID" in header:
            existing_ids = {str(r.get("TagID", "")).strip() for r in rows}

    seed_rows = []
    for raw in iter_seed_tags():
        if raw["TagID"] in existing_ids:
            continue
        category_name = clean_text(raw.get("DefaultCategoryName"), 60)
        category = find_category_by_name(category_name, "Expenditure") if category_name else None
        seed_rows.append(
            {
                "TagID": raw["TagID"],
                "Name": raw["Name"],
                "Type": raw["Type"],
                "Aliases": raw.get("Aliases", ""),
                "ParentTag": raw.get("ParentTag", ""),
                "DefaultCategoryID": category["CategoryID"] if category else "",
                "IsActive": "TRUE",
            }
        )
    if seed_rows:
        append_rows("Tags", seed_rows)
    summary["tags"] = f"seeded {len(seed_rows)} tags"


def _seed_settings(summary: dict, owner: str) -> None:
    existing = read_values("Settings")
    existing_users: set[str] = set()
    if existing:
        header, rows = _rows_from_values(existing)
        if "User" in header:
            existing_users = {
                str(r.get("User", "")).strip().lower() for r in rows if r.get("User")
            }
    new_rows = []
    if owner.strip().lower() not in existing_users:
        new_rows.append({"User": owner, **DEFAULT_SETTINGS})
    if new_rows:
        append_rows("Settings", new_rows)
    summary["settings"] = f"seeded {len(new_rows)} owner settings"


def _write_meta(summary: dict, owner: str) -> None:
    values = read_values("Meta")
    header, rows = _rows_from_values(values)
    records = {str(r.get("Key", "")).strip(): dict(r) for r in rows if str(r.get("Key", "")).strip()}
    # The sheet has one owner now; drop the old multi-user marker.
    records.pop("Users", None)
    updates = {
        "SchemaVersion": SCHEMA_VERSION,
        "AppVersion": APP_VERSION,
        "BootstrappedAt": now_iso(),
        "LexiconVersion": str(load_lexicon().get("version", "1")),
        "Owner": owner,
        "LegacyBackups": ", ".join(summary["backups"]),
        "BootstrapSummary": json.dumps(
            {k: v for k, v in summary.items() if k not in {"backups", "backups_skipped"}},
            default=str,
        ),
    }
    for key, value in updates.items():
        record = records.get(key, {"Key": key, "Value": "", "UpdatedAt": ""})
        record["Value"] = value
        record["UpdatedAt"] = now_iso()
        records[key] = record
    write_tab("Meta", list(records.values()), headers=V2_SCHEMAS["Meta"])


def bootstrap_uncached(owner: str) -> dict:
    summary: dict = {
        "backups": [],
        "backups_skipped": [],
        "started": now_iso(),
    }
    for name in LEGACY_TABS:
        _backup_tab(name, summary)

    ensure_all_tabs()

    # New tabs may have been created just above. Repair empty/wrong-header tabs.
    for name in V2_SCHEMAS:
        if name in {"Accounts", "Categories"}:
            continue
        values = read_values(name)
        if not values:
            write_raw(name, [V2_SCHEMAS[name]])
            continue
        header = [str(cell).strip() for cell in values[0]]
        has_data = len(values) > 1 and any(any(str(c).strip() for c in row) for row in values[1:])
        if header != V2_SCHEMAS[name] and not has_data:
            write_raw(name, [V2_SCHEMAS[name]])

    _migrate_accounts(summary, owner)
    _migrate_categories(summary)
    _seed_tags(summary)
    _seed_settings(summary, owner)
    _write_meta(summary, owner)

    clear_cache()
    summary["finished"] = now_iso()
    return summary


@st.cache_resource(show_spinner=False)
def _bootstrap_once(spreadsheet_id: str, owner: str) -> dict:
    return bootstrap_uncached(owner)


def bootstrap(spreadsheet_id: str, owner: str) -> dict:
    """Run bootstrap once per spreadsheet/owner pair and reuse the result."""
    try:
        active = st.session_state.get("active_source")
    except Exception:
        active = None
    if active and active != owner:
        raise RuntimeError("The requested spreadsheet is not the active data source.")
    return _bootstrap_once(spreadsheet_id, owner)
