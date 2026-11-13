"""Account and card registry.

Only nicknames and opaque IDs are stored. No account or card numbers.
"""

from __future__ import annotations

from datetime import date

from src.db.repo import append_rows, clear_cache, read_tab, update_row
from src.db.schemas import (
    ACCOUNT_KINDS,
    CASH_ACCOUNT_KINDS,
    KIND_LABELS,
)
from src.utils.ids import as_int, clean_text, new_id, now_iso
from src.utils.privacy import sanitize_free_text, validate_nickname


def list_accounts(
    user: str,
    active_only: bool = True,
    kinds: list[str] | None = None,
) -> list[dict]:
    df = read_tab("Accounts")
    if df.empty:
        return []
    rows = df.to_dict("records")
    rows = [r for r in rows if str(r.get("User", "")).strip() == user]
    if active_only:
        rows = [
            r
            for r in rows
            if str(r.get("IsActive", "TRUE")).strip().lower()
            not in {"false", "0", "no", "off"}
        ]
    if kinds:
        wanted = {k.strip().lower() for k in kinds}
        rows = [r for r in rows if str(r.get("Kind", "")).strip().lower() in wanted]
    kind_order = {
        kind: index
        for index, kind in enumerate([*CASH_ACCOUNT_KINDS, "credit_card", "loan"])
    }
    rows.sort(
        key=lambda r: (
            kind_order.get(str(r.get("Kind", "")).strip().lower(), 99),
            str(r.get("Nickname", "")).lower(),
        )
    )
    return rows


def account_map(user: str, active_only: bool = False) -> dict[str, dict]:
    return {str(r.get("AccountID")): r for r in list_accounts(user, active_only=active_only)}


def get_account(account_id_value: str) -> dict | None:
    df = read_tab("Accounts")
    if df.empty or "AccountID" not in df.columns:
        return None
    match = df[df["AccountID"].astype(str).str.strip() == str(account_id_value).strip()]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def account_label(row: dict) -> str:
    nickname = str(row.get("Nickname", "")).strip() or "Unnamed"
    kind = KIND_LABELS.get(str(row.get("Kind", "")).strip(), str(row.get("Kind", "")))
    return f"{nickname} · {kind}"


def account_options(
    user: str,
    kinds: list[str] | None = None,
    include_inactive: bool = False,
) -> tuple[list[str], dict[str, str]]:
    rows = list_accounts(user, active_only=not include_inactive, kinds=kinds)
    labels = {account_label(r): str(r.get("AccountID")) for r in rows}
    return list(labels.keys()), labels


def cash_accounts(user: str) -> list[dict]:
    return list_accounts(user, kinds=CASH_ACCOUNT_KINDS)


def cards(user: str) -> list[dict]:
    return list_accounts(user, kinds=["credit_card"])


def find_nickname_duplicate(user: str, nickname: str, kind: str | None = None) -> dict | None:
    target = clean_text(nickname).lower()
    for row in list_accounts(user, active_only=False):
        if str(row.get("Nickname", "")).strip().lower() == target:
            if kind is None or str(row.get("Kind", "")).strip().lower() == kind.lower():
                return row
    return None


def create_account(
    user: str,
    nickname: str,
    kind: str,
    institution: str = "",
    currency: str = "INR",
    opening_balance_paise: int = 0,
    opening_date: date | str | None = None,
    credit_limit_paise: int = 0,
    statement_day: int | str | None = None,
    due_day: int | str | None = None,
    notes: str = "",
    allow_duplicate: bool = False,
) -> dict:
    nickname = validate_nickname(nickname)
    kind = str(kind or "").strip().lower()
    if kind not in ACCOUNT_KINDS:
        raise ValueError(f"Unknown account kind: {kind}")
    duplicate = find_nickname_duplicate(user, nickname)
    if duplicate and not allow_duplicate:
        raise ValueError(
            "An account or card with this nickname already exists. Use a different nickname or confirm the duplicate."
        )

    opening = int(opening_balance_paise or 0)
    if kind in {"credit_card", "loan"}:
        opening = -abs(opening)
    else:
        opening = abs(opening)

    row = {
        "AccountID": new_id("acc"),
        "Timestamp": now_iso(),
        "User": user,
        "Nickname": nickname,
        "Kind": kind,
        "Institution": sanitize_free_text(institution, 80),
        "Currency": clean_text(currency, 8).upper() or "INR",
        "OpeningBalance": opening,
        "OpeningDate": str(opening_date or date.today()),
        "CreditLimit": abs(int(credit_limit_paise or 0)) if kind == "credit_card" else 0,
        "StatementDay": str(statement_day or "").strip(),
        "DueDay": str(due_day or "").strip(),
        "IsActive": "TRUE",
        "Notes": sanitize_free_text(notes, 240),
    }
    append_rows("Accounts", [row])
    return row


def set_account_active(account_id_value: str, active: bool) -> bool:
    row = get_account(account_id_value)
    if not row:
        return False
    row["IsActive"] = "TRUE" if active else "FALSE"
    return update_row("Accounts", "AccountID", account_id_value, row)


def update_account_fields(account_id_value: str, **fields) -> bool:
    row = get_account(account_id_value)
    if not row:
        return False
    allowed = {
        "Nickname",
        "Institution",
        "Currency",
        "CreditLimit",
        "StatementDay",
        "DueDay",
        "IsActive",
        "Notes",
    }
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "Nickname":
            value = validate_nickname(value)
        if key == "Institution":
            value = sanitize_free_text(value, 80)
        if key == "Notes":
            value = sanitize_free_text(value, 240)
        row[key] = value
    return update_row("Accounts", "AccountID", account_id_value, row)
