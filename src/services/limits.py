"""Spending limits / budgets. Reminder logic is intentionally read-only in v1."""

from __future__ import annotations

from datetime import date

from src.db.repo import append_rows, read_tab, update_row
from src.services.ledger import recent_entries
from src.utils.ids import as_int, new_id

SCOPES = ["overall", "category", "account"]
PERIODS = ["monthly", "specific_month"]


def list_limits(user: str, active_only: bool = True) -> list[dict]:
    df = read_tab("Limits")
    if df.empty:
        return []
    rows = [r for r in df.to_dict("records") if str(r.get("User", "")).strip() == user]
    if active_only:
        rows = [
            r
            for r in rows
            if str(r.get("IsActive", "TRUE")).strip().lower()
            not in {"false", "0", "no", "off"}
        ]
    return rows


def save_limit(
    user: str,
    scope: str,
    period: str,
    amount_paise: int,
    target_id: str = "",
    warn_at_pct: int = 80,
    is_active: bool = True,
) -> dict:
    scope = str(scope or "overall").strip().lower()
    if scope not in SCOPES:
        raise ValueError("Unknown limit scope.")
    if scope != "overall" and not target_id:
        raise ValueError("Choose a category or account for this limit.")
    amount = int(amount_paise or 0)
    if amount <= 0:
        raise ValueError("Limit must be greater than zero.")
    row = {
        "LimitID": new_id("lim"),
        "User": user,
        "Scope": scope,
        "TargetID": target_id,
        "Period": str(period or "monthly"),
        "Amount": amount,
        "WarnAtPct": max(1, min(100, int(warn_at_pct or 80))),
        "IsActive": "TRUE" if is_active else "FALSE",
    }
    append_rows("Limits", [row])
    return row


def set_limit_active(limit_id: str, active: bool) -> bool:
    df = read_tab("Limits")
    if df.empty:
        return False
    for row in df.to_dict("records"):
        if str(row.get("LimitID", "")).strip() == str(limit_id).strip():
            row["IsActive"] = "TRUE" if active else "FALSE"
            return update_row("Limits", "LimitID", limit_id, row)
    return False


def spent_for_limit(limit: dict, user: str, as_of: date | None = None) -> int:
    as_of = as_of or date.today()
    period = str(limit.get("Period", "monthly"))
    rows = recent_entries(user, limit=None)
    reversed_ids = {
        str(row.get("LinkedEntryID", "")).strip()
        for row in rows
        if str(row.get("Type", "")).strip().lower() == "reversal"
        and str(row.get("Status", "")).strip().lower() not in {"pending", "void", "cancelled"}
        and str(row.get("LinkedEntryID", "")).strip()
    }
    total = 0
    scope = str(limit.get("Scope", "")).strip().lower()
    target = str(limit.get("TargetID", "")).strip()
    for row in rows:
        if str(row.get("Status", "")).strip().lower() in {"pending", "void", "cancelled"}:
            continue
        if str(row.get("EntryID", "")).strip() in reversed_ids:
            continue
        if str(row.get("Type", "")).strip().lower() != "expense":
            continue
        row_date = str(row.get("Date", ""))[:10]
        if period.startswith("month:"):
            month = period.split(":", 1)[1]
            if not row_date.startswith(month):
                continue
        else:
            if not row_date.startswith(as_of.strftime("%Y-%m")):
                continue
        if scope == "category" and str(row.get("CategoryID", "")).strip() != target:
            continue
        if scope == "account" and str(row.get("AccountID", "")).strip() != target:
            continue
        total += as_int(row.get("Amount"))
    return total
