"""Per-user settings and payment-method account defaults."""

from __future__ import annotations

from src.db.repo import append_rows, read_tab, update_row, write_tab
from src.db.schemas import CASH_ACCOUNT_KINDS, DEFAULT_SETTINGS
from src.services.accounts import get_account, list_accounts

METHOD_FALLBACK_KINDS = {
    "card": ["credit_card"],
    "bill_payment": CASH_ACCOUNT_KINDS,
    "cash": ["cash", *CASH_ACCOUNT_KINDS],
    "wallet": ["wallet", *CASH_ACCOUNT_KINDS],
}


def get_settings(user: str) -> dict:
    df = read_tab("Settings")
    row: dict = {}
    if not df.empty and "User" in df.columns:
        match = df[df["User"].astype(str).str.strip() == user]
        if not match.empty:
            row = match.iloc[0].to_dict()
    merged = dict(DEFAULT_SETTINGS)
    for key, value in row.items():
        if str(value).strip() != "":
            merged[key] = value
    merged["User"] = user
    return merged


def save_settings(user: str, values: dict) -> bool:
    df = read_tab("Settings")
    current: dict = {"User": user, **DEFAULT_SETTINGS}
    exists = False
    if not df.empty and "User" in df.columns:
        match = df[df["User"].astype(str).str.strip() == user]
        if not match.empty:
            current.update(match.iloc[0].to_dict())
            exists = True
    for key in DEFAULT_SETTINGS:
        if key in values:
            current[key] = values[key]
    if exists:
        return update_row("Settings", "User", user, current)
    append_rows("Settings", [current])
    return True


def _all_payment_defaults() -> list[dict]:
    df = read_tab("PaymentDefaults")
    return [] if df.empty else df.to_dict("records")


def list_payment_defaults(user: str) -> list[dict]:
    return [r for r in _all_payment_defaults() if str(r.get("User", "")).strip() == user]


def _default_row(user: str, method: str) -> dict | None:
    for row in list_payment_defaults(user):
        if str(row.get("Method", "")).strip().lower() == method.strip().lower():
            return row
    return None


def resolve_default_account(user: str, method: str) -> dict | None:
    """Explicit default -> last used -> first active account of a sensible kind."""
    method = str(method or "").strip().lower()
    row = _default_row(user, method)
    if row:
        for key in ("DefaultAccountID", "LastUsedAccountID"):
            account = get_account(str(row.get(key, "")).strip())
            if account and str(account.get("User", "")).strip() == user:
                if str(account.get("IsActive", "TRUE")).strip().lower() not in {"false", "0", "no"}:
                    return account
    kinds = METHOD_FALLBACK_KINDS.get(method)
    candidates = list_accounts(user, kinds=kinds) if kinds else []
    if not candidates and method == "card":
        candidates = list_accounts(user)
    if not candidates:
        candidates = list_accounts(user)
    return candidates[0] if candidates else None


def _upsert_default(record: dict) -> None:
    rows = _all_payment_defaults()
    user = str(record.get("User", "")).strip()
    method = str(record.get("Method", "")).strip().lower()
    replaced = False
    for index, row in enumerate(rows):
        if (
            str(row.get("User", "")).strip() == user
            and str(row.get("Method", "")).strip().lower() == method
        ):
            rows[index] = {**row, **record}
            replaced = True
            break
    if not replaced:
        rows.append(record)
    write_tab("PaymentDefaults", rows)


def save_payment_default(
    user: str,
    method: str,
    default_account_id: str = "",
    last_used_account_id: str = "",
) -> None:
    method = str(method or "").strip().lower()
    record = {"User": user, "Method": method, "IsActive": "TRUE"}
    if default_account_id:
        record["DefaultAccountID"] = default_account_id
    if last_used_account_id:
        record["LastUsedAccountID"] = last_used_account_id
    _upsert_default(record)


def save_payment_defaults(user: str, defaults: dict[str, str]) -> None:
    """Save several method -> AccountID mappings in one sheet write."""
    rows = _all_payment_defaults()
    index = {
        (
            str(row.get("User", "")).strip(),
            str(row.get("Method", "")).strip().lower(),
        ): position
        for position, row in enumerate(rows)
    }
    for method, account_id in defaults.items():
        method = str(method or "").strip().lower()
        key = (str(user).strip(), method)
        record = dict(rows[index[key]]) if key in index else {
            "User": user,
            "Method": method,
            "DefaultAccountID": "",
            "LastUsedAccountID": "",
            "IsActive": "TRUE",
        }
        if account_id:
            record["DefaultAccountID"] = account_id
        record["IsActive"] = "TRUE"
        if key in index:
            rows[index[key]] = record
        else:
            index[key] = len(rows)
            rows.append(record)
    write_tab("PaymentDefaults", rows)


def remember_last_account(user: str, method: str, account_id_value: str) -> None:
    if not account_id_value:
        return
    method = str(method or "").strip().lower()
    current = _default_row(user, method) or {
        "User": user,
        "Method": method,
        "DefaultAccountID": "",
        "IsActive": "TRUE",
    }
    record = dict(current)
    record["LastUsedAccountID"] = account_id_value
    _upsert_default(record)
