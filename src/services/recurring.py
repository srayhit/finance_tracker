"""Recurring bill reminders. No auto-posting in v1."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from src.db.repo import append_rows, read_tab, update_row
from src.utils.ids import as_int, clean_text, new_id

FREQUENCIES = ["weekly", "monthly", "quarterly", "yearly"]
NOTIFY_CHANNELS = ["in_app", "email", "both"]


def list_rules(user: str, active_only: bool = True) -> list[dict]:
    df = read_tab("RecurringRules")
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
    rows.sort(key=lambda r: str(r.get("NextDueDate", "")))
    return rows


def save_rule(
    user: str,
    name: str,
    amount_paise: int,
    account_id: str,
    category_id: str,
    frequency: str,
    next_due_date: date | str,
    remind_days_before: int = 7,
    notify_via: str = "in_app",
    auto_post: bool = False,
    is_active: bool = True,
) -> dict:
    name = clean_text(name, 80)
    if not name:
        raise ValueError("Bill name is required.")
    amount = int(amount_paise or 0)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    frequency = str(frequency or "monthly").strip().lower()
    if frequency not in FREQUENCIES:
        raise ValueError("Unknown bill frequency.")
    row = {
        "RuleID": new_id("rec"),
        "User": user,
        "Name": name,
        "Amount": amount,
        "AccountID": account_id,
        "CategoryID": category_id,
        "Frequency": frequency,
        "NextDueDate": str(next_due_date),
        "RemindDaysBefore": max(0, int(remind_days_before or 7)),
        "NotifyVia": str(notify_via or "in_app"),
        "AutoPost": "TRUE" if auto_post else "FALSE",
        "IsActive": "TRUE" if is_active else "FALSE",
        "LastMatchedEntryID": "",
        "LastPaidDate": "",
        "LastPostedEntryID": "",
    }
    append_rows("RecurringRules", [row])
    return row


def set_rule_active(rule_id: str, active: bool) -> bool:
    df = read_tab("RecurringRules")
    if df.empty:
        return False
    for row in df.to_dict("records"):
        if str(row.get("RuleID", "")).strip() == str(rule_id).strip():
            row["IsActive"] = "TRUE" if active else "FALSE"
            return update_row("RecurringRules", "RuleID", rule_id, row)
    return False


def next_due_date(current: date, frequency: str) -> date:
    frequency = str(frequency or "monthly").lower()
    if frequency == "weekly":
        return current + timedelta(days=7)
    if frequency == "quarterly":
        month = current.month + 3
        year = current.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(current.day, 28)
        return date(year, month, day)
    if frequency == "yearly":
        return date(current.year + 1, current.month, min(current.day, 28))
    month = current.month + 1
    year = current.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(current.day, 28)
    return date(year, month, day)


def mark_paid(rule_id: str, paid_date: date | str | None = None) -> bool:
    df = read_tab("RecurringRules")
    if df.empty:
        return False
    paid = str(paid_date or date.today())
    for row in df.to_dict("records"):
        if str(row.get("RuleID", "")).strip() != str(rule_id).strip():
            continue
        try:
            base = datetime.strptime(str(row.get("NextDueDate", ""))[:10], "%Y-%m-%d").date()
        except Exception:
            base = date.today()
        row["LastPaidDate"] = paid
        row["NextDueDate"] = next_due_date(base, str(row.get("Frequency", "monthly"))).isoformat()
        return update_row("RecurringRules", "RuleID", rule_id, row)
    return False


def upcoming_rules(user: str, within_days: int = 30, as_of: date | None = None) -> list[dict]:
    as_of = as_of or date.today()
    rows = []
    for row in list_rules(user):
        due_text = str(row.get("NextDueDate", ""))[:10]
        try:
            due = datetime.strptime(due_text, "%Y-%m-%d").date()
        except Exception:
            continue
        days = (due - as_of).days
        if days <= within_days:
            item = dict(row)
            item["DaysUntilDue"] = days
            rows.append(item)
    rows.sort(key=lambda r: r["DaysUntilDue"])
    return rows
