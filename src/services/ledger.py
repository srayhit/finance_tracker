"""Append-only cash ledger: posting, balances, duplicates and reversal."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from rapidfuzz import fuzz

from src.db.repo import (
    append_rows,
    read_tab,
    read_tab_uncached,
    update_row,
)
from src.services.accounts import account_map, list_accounts
from src.services.settings import get_settings
from src.utils.ids import as_int, clean_text, new_id, now_iso, truthy

OUTFLOW_TYPES = {"expense", "stock_buy", "asset_purchase"}
INFLOW_TYPES = {"income", "stock_sell", "asset_sale"}
TRANSFER_TYPES = {"transfer"}
ADJUSTMENT_TYPES = {"adjustment"}
IGNORED_STATUSES = {"pending", "void", "cancelled", "failed"}


def new_ledger_row(
    user: str,
    entry_type: str,
    entry_date: date | str,
    amount_paise: int,
    account_id: str,
    counter_account_id: str = "",
    fees_paise: int = 0,
    tax_withheld_paise: int = 0,
    category_id: str = "",
    description: str = "",
    tag_ids: list[str] | None = None,
    is_private: bool = False,
    client_request_id: str = "",
    linked_trade_id: str = "",
    linked_entry_id: str = "",
    duplicate_of_entry_id: str = "",
) -> dict:
    return {
        "EntryID": new_id("txn"),
        "ClientRequestID": client_request_id or new_id("req"),
        "IdempotencyKey": "",
        "WriteBatchID": "",
        "Timestamp": now_iso(),
        "Date": str(entry_date),
        "User": user,
        "Type": entry_type,
        "AccountID": account_id,
        "CounterAccountID": counter_account_id,
        "Amount": int(amount_paise or 0),
        "Fees": int(fees_paise or 0),
        "TaxWithheld": int(tax_withheld_paise or 0),
        "CategoryID": category_id,
        "Description": clean_text(description, 120),
        "Tags": ", ".join(dict.fromkeys(tag_ids or [])),
        "IsPrivate": "TRUE" if is_private else "FALSE",
        "Status": "pending",
        "LinkedEntryID": linked_entry_id,
        "LinkedTradeID": linked_trade_id,
        "DuplicateOfEntryID": duplicate_of_entry_id,
        "CreatedBy": user,
        "UpdatedAt": now_iso(),
        "UpdatedBy": user,
    }


def _is_effective(row: dict) -> bool:
    return str(row.get("Status", "")).strip().lower() not in IGNORED_STATUSES


def _is_posted(row: dict) -> bool:
    return str(row.get("Status", "")).strip().lower() in {"posted", ""}


def _ledger_rows(user: str | None = None) -> list[dict]:
    df = read_tab("Ledger")
    if df.empty:
        return []
    rows = df.to_dict("records")
    if user is not None:
        rows = [r for r in rows if str(r.get("User", "")).strip() == user]
    return rows


def _entry_index(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("EntryID", "")).strip(): r for r in rows if str(r.get("EntryID", "")).strip()}


def _effects_for(row: dict, index: dict[str, dict] | None = None) -> dict[str, int]:
    """Signed effect of one posted ledger row, keyed by AccountID."""
    amount = as_int(row.get("Amount"))
    entry_type = str(row.get("Type", "")).strip().lower()
    account_id = str(row.get("AccountID", "")).strip()
    counter_id = str(row.get("CounterAccountID", "")).strip()

    if entry_type == "reversal":
        original_id = str(row.get("LinkedEntryID", "")).strip()
        original = (index or {}).get(original_id)
        if not original:
            return {}
        original_effects = _effects_for(original, index)
        return {key: -value for key, value in original_effects.items()}

    effects: dict[str, int] = {}
    if entry_type in OUTFLOW_TYPES:
        if account_id:
            effects[account_id] = -amount
    elif entry_type in INFLOW_TYPES:
        if account_id:
            effects[account_id] = amount
    elif entry_type in TRANSFER_TYPES:
        if account_id:
            effects[account_id] = -amount
        if counter_id:
            effects[counter_id] = amount
    elif entry_type in ADJUSTMENT_TYPES:
        if account_id:
            effects[account_id] = amount
    elif entry_type == "expense":
        if account_id:
            effects[account_id] = -amount
    return effects


def compute_balances(
    user: str,
    as_of: date | str | None = None,
    active_only: bool = False,
) -> dict[str, int]:
    accounts = list_accounts(user, active_only=active_only)
    balances = {
        str(row.get("AccountID")): as_int(row.get("OpeningBalance"))
        for row in accounts
    }
    cutoff = str(as_of or "")
    rows = [r for r in _ledger_rows(user) if _is_effective(r)]
    if cutoff:
        rows = [r for r in rows if str(r.get("Date", ""))[:10] <= cutoff]
    index = _entry_index(_ledger_rows(user))
    for row in rows:
        for account_id, effect in _effects_for(row, index).items():
            if account_id in balances:
                balances[account_id] += effect
    return balances


def account_balance(account_id_value: str, user: str, as_of: date | str | None = None) -> int:
    return compute_balances(user, as_of=as_of, active_only=False).get(
        str(account_id_value), 0
    )


def outstanding(account: dict, balance_paise: int) -> int:
    kind = str(account.get("Kind", "")).strip().lower()
    if kind in {"credit_card", "loan"}:
        return max(0, -int(balance_paise or 0))
    return int(balance_paise or 0)


def available_limit(account: dict, balance_paise: int) -> int:
    limit = as_int(account.get("CreditLimit"))
    if str(account.get("Kind", "")).strip().lower() != "credit_card":
        return 0
    return max(0, limit - outstanding(account, balance_paise))


def recent_entries(user: str, limit: int | None = 50) -> list[dict]:
    rows = _ledger_rows(user)
    rows.sort(key=lambda r: (str(r.get("Date", "")), str(r.get("Timestamp", ""))), reverse=True)
    return rows if limit is None else rows[:limit]


def get_entry(entry_id_value: str, user: str | None = None) -> dict | None:
    for row in _ledger_rows(user):
        if str(row.get("EntryID", "")).strip() == str(entry_id_value).strip():
            return row
    return None


def find_by_client_request_id(user: str, client_request_id: str) -> dict | None:
    if not client_request_id:
        return None
    for row in _ledger_rows(user):
        if str(row.get("ClientRequestID", "")).strip() == str(client_request_id).strip():
            return row
    return None


def reversed_entry_ids(user: str) -> set[str]:
    ids = set()
    for row in _ledger_rows(user):
        if str(row.get("Type", "")).strip().lower() == "reversal" and _is_effective(row):
            linked = str(row.get("LinkedEntryID", "")).strip()
            if linked:
                ids.add(linked)
    return ids


def _date_diff_days(left: object, right: object) -> int:
    try:
        a = datetime.strptime(str(left)[:10], "%Y-%m-%d").date()
        b = datetime.strptime(str(right)[:10], "%Y-%m-%d").date()
        return abs((a - b).days)
    except Exception:
        return 10_000


def _amount_close(a: int, b: int, pct: float) -> bool:
    if a == b:
        return True
    base = max(abs(a), abs(b), 1)
    return abs(a - b) / base * 100.0 <= pct


def _description_close(a: object, b: object, threshold: float) -> bool:
    left = clean_text(a).lower()
    right = clean_text(b).lower()
    if not left and not right:
        return True
    if not left or not right:
        return True
    return fuzz.ratio(left, right) >= threshold


def find_near_duplicates(
    user: str,
    entry_type: str,
    entry_date: date | str,
    amount_paise: int,
    account_id: str = "",
    counter_account_id: str = "",
    description: str = "",
    asset_id: str = "",
    quantity: float = 0,
    unit_price: int = 0,
    exclude_entry_id: str = "",
) -> list[dict]:
    settings = get_settings(user)
    window_days = as_int(settings.get("DuplicateWindowDays"), 45)
    date_days = as_int(settings.get("DuplicateDateDays"), 2)
    amount_pct = float(settings.get("DuplicateAmountPct") or 2)
    description_pct = float(settings.get("DuplicateDescriptionPct") or 85)
    entry_type = str(entry_type or "").strip().lower()
    reversed_ids = reversed_entry_ids(user)
    candidates: list[dict] = []

    if entry_type in {"expense", "income"}:
        for row in _ledger_rows(user):
            if not _is_effective(row) or str(row.get("EntryID", "")) == exclude_entry_id:
                continue
            if str(row.get("EntryID", "")) in reversed_ids:
                continue
            if str(row.get("Type", "")).strip().lower() != entry_type:
                continue
            if str(row.get("AccountID", "")).strip() != str(account_id).strip():
                continue
            if _date_diff_days(row.get("Date"), entry_date) > date_days:
                continue
            if not _amount_close(as_int(row.get("Amount")), amount_paise, amount_pct):
                continue
            similarity = fuzz.ratio(
                clean_text(row.get("Description")).lower(), clean_text(description).lower()
            )
            if not _description_close(row.get("Description"), description, description_pct):
                continue
            candidates.append(
                {
                    "kind": "ledger",
                    "row": row,
                    "score": max(similarity / 100.0, 0.8),
                    "reason": "same type, account, date and amount",
                }
            )
    elif entry_type in {"transfer", "card_payment"}:
        for row in _ledger_rows(user):
            if not _is_effective(row) or str(row.get("EntryID", "")) == exclude_entry_id:
                continue
            if str(row.get("EntryID", "")) in reversed_ids:
                continue
            if str(row.get("Type", "")).strip().lower() != "transfer":
                continue
            if str(row.get("AccountID", "")).strip() != str(account_id).strip():
                continue
            if str(row.get("CounterAccountID", "")).strip() != str(counter_account_id).strip():
                continue
            if _date_diff_days(row.get("Date"), entry_date) > 1:
                continue
            if as_int(row.get("Amount")) != amount_paise:
                continue
            candidates.append(
                {
                    "kind": "ledger",
                    "row": row,
                    "score": 1.0,
                    "reason": "same source, destination and amount",
                }
            )
    elif entry_type in {"stock_buy", "stock_sell", "asset_purchase", "asset_sale"}:
        df = read_tab("InvestmentLedger")
        if not df.empty:
            side = "buy" if entry_type in {"stock_buy", "asset_purchase"} else "sell"
            for row in df.to_dict("records"):
                if str(row.get("User", "")).strip() != user:
                    continue
                if str(row.get("Status", "")).strip().lower() in IGNORED_STATUSES:
                    continue
                if str(row.get("AssetID", "")).strip() != str(asset_id).strip():
                    continue
                if str(row.get("Side", "")).strip().lower() != side:
                    continue
                if _date_diff_days(row.get("Date"), entry_date) > 1:
                    continue
                qty = float(row.get("Quantity") or 0)
                price = as_int(row.get("UnitPrice"))
                if qty and quantity and abs(qty - quantity) / max(qty, quantity) > 0.01:
                    continue
                if price and unit_price and not _amount_close(price, unit_price, 1.0):
                    continue
                candidates.append(
                    {
                        "kind": "trade",
                        "row": row,
                        "score": 1.0,
                        "reason": "same asset, side, quantity and price",
                    }
                )

    candidates.sort(key=lambda c: str(c["row"].get("Date", "")), reverse=True)
    return candidates[:5]


def _verify_ids(tab: str, id_column: str, ids: list[str]) -> bool:
    df = read_tab_uncached(tab)
    if df.empty or id_column not in df.columns:
        return False
    present = set(df[id_column].astype(str).str.strip())
    return all(value in present for value in ids)


def _verify_posted(tab: str, id_column: str, ids: list[str]) -> bool:
    if not ids:
        return True
    df = read_tab_uncached(tab)
    if df.empty or id_column not in df.columns or "Status" not in df.columns:
        return False
    rows = df.to_dict("records")
    status = {
        str(row.get(id_column, "")).strip(): str(row.get("Status", "")).strip().lower()
        for row in rows
    }
    return all(status.get(value) == "posted" for value in ids)


def finalize_batch(batch_id: str, user: str) -> int:
    """Promote a pending batch to posted after verifying every row exists."""
    count = 0
    df = read_tab_uncached("Ledger")
    if not df.empty:
        for row in df.to_dict("records"):
            if str(row.get("WriteBatchID", "")).strip() != str(batch_id).strip():
                continue
            if str(row.get("Status", "")).strip().lower() == "posted":
                continue
            row["Status"] = "posted"
            row["UpdatedAt"] = now_iso()
            row["UpdatedBy"] = user
            if update_row("Ledger", "EntryID", str(row.get("EntryID")), row):
                count += 1
    df = read_tab_uncached("InvestmentLedger")
    if not df.empty:
        for row in df.to_dict("records"):
            if str(row.get("WriteBatchID", "")).strip() != str(batch_id).strip():
                continue
            if str(row.get("Status", "")).strip().lower() == "posted":
                continue
            row["Status"] = "posted"
            if update_row("InvestmentLedger", "TradeID", str(row.get("TradeID")), row):
                count += 1
    return count


def commit_batch(
    user: str,
    ledger_rows: list[dict],
    trade_rows: list[dict] | None = None,
    audit_action: str = "post_entry",
    audit_meta: dict | None = None,
    default_method: str = "",
    source_account_id: str = "",
) -> dict:
    ledger_rows = [dict(row) for row in ledger_rows if row]
    trade_rows = [dict(row) for row in (trade_rows or []) if row]
    if not ledger_rows:
        raise ValueError("Nothing to save.")

    existing = find_by_client_request_id(user, str(ledger_rows[0].get("ClientRequestID", "")))
    if existing:
        batch_id = str(existing.get("WriteBatchID", "")).strip()
        if batch_id and str(existing.get("Status", "")).strip().lower() == "pending":
            try:
                finalize_batch(batch_id, user)
            except Exception:
                pass
        return {
            "entry_ids": [str(existing.get("EntryID"))],
            "trade_ids": [],
            "batch_id": batch_id,
            "already_saved": True,
        }

    batch_id = new_id("bat")
    timestamp = now_iso()
    for row in ledger_rows:
        row["WriteBatchID"] = batch_id
        row["Status"] = "pending"
        row["Timestamp"] = row.get("Timestamp") or timestamp
        row["UpdatedAt"] = timestamp
        row["UpdatedBy"] = user
        row.setdefault("User", user)
    for row in trade_rows:
        row["WriteBatchID"] = batch_id
        row["Status"] = "pending"
        row["Timestamp"] = row.get("Timestamp") or timestamp
        row.setdefault("User", user)

    append_rows("Ledger", ledger_rows)
    if trade_rows:
        append_rows("InvestmentLedger", trade_rows)

    ledger_ids = [str(row.get("EntryID")) for row in ledger_rows if row.get("EntryID")]
    trade_ids = [str(row.get("TradeID")) for row in trade_rows if row.get("TradeID")]
    if not _verify_ids("Ledger", "EntryID", ledger_ids):
        raise RuntimeError(
            f"Saved rows could not be verified. Batch {batch_id} stays pending; retry finalize."
        )
    if trade_ids and not _verify_ids("InvestmentLedger", "TradeID", trade_ids):
        raise RuntimeError(
            f"Trade rows could not be verified. Batch {batch_id} stays pending; retry finalize."
        )

    finalize_batch(batch_id, user)
    if not _verify_posted("Ledger", "EntryID", ledger_ids):
        raise RuntimeError(
            f"Batch {batch_id} was written but is still pending. Retry the same entry to finalize it."
        )
    if trade_ids and not _verify_posted("InvestmentLedger", "TradeID", trade_ids):
        raise RuntimeError(
            f"Trade batch {batch_id} was written but is still pending. Retry the same entry to finalize it."
        )

    after = {
        "entry_ids": ledger_ids,
        "trade_ids": trade_ids,
        "batch_id": batch_id,
        **(audit_meta or {}),
    }
    try:
        append_rows(
            "Audit",
            [
                {
                    "Timestamp": now_iso(),
                    "User": user,
                    "Action": audit_action,
                    "Tab": "Ledger" if not trade_ids else "Ledger+InvestmentLedger",
                    "RecordID": ", ".join(ledger_ids),
                    "Before": "",
                    "After": json.dumps(after, default=str)[:2000],
                    "WriteBatchID": batch_id,
                }
            ],
        )
    except Exception:
        pass
    if default_method and source_account_id:
        try:
            from src.services.settings import remember_last_account

            remember_last_account(user, default_method, source_account_id)
        except Exception:
            pass
    return {
        "entry_ids": ledger_ids,
        "trade_ids": trade_ids,
        "batch_id": batch_id,
        "already_saved": False,
    }


def reverse_entry(
    user: str,
    entry_id_value: str,
    reason: str,
    reversal_date: date | str | None = None,
) -> dict:
    original = get_entry(entry_id_value, user)
    if not original:
        raise ValueError("Entry not found.")
    if str(original.get("Type", "")).strip().lower() == "reversal":
        raise ValueError("A reversal entry cannot be reversed.")
    if str(original.get("EntryID", "")).strip() in reversed_entry_ids(user):
        raise ValueError("This entry has already been reversed.")
    reason = clean_text(reason, 160)
    if not reason:
        raise ValueError("A reason is required for a reversal.")

    reversal_date = str(reversal_date or date.today())
    reversal = new_ledger_row(
        user=user,
        entry_type="reversal",
        entry_date=reversal_date,
        amount_paise=as_int(original.get("Amount")),
        account_id=str(original.get("AccountID", "")),
        counter_account_id=str(original.get("CounterAccountID", "")),
        fees_paise=as_int(original.get("Fees")),
        category_id=str(original.get("CategoryID", "")),
        description=f"Reversal: {original.get('Description', '')}",
        tag_ids=[
            tag.strip()
            for tag in str(original.get("Tags", "")).split(",")
            if tag.strip()
        ],
        is_private=truthy(original.get("IsPrivate")),
        linked_entry_id=str(original.get("EntryID", "")),
    )
    trade_rows = []
    original_trade_id = str(original.get("LinkedTradeID", "")).strip()
    if original_trade_id:
        df = read_tab("InvestmentLedger")
        if not df.empty:
            for trade in df.to_dict("records"):
                if str(trade.get("TradeID", "")).strip() != original_trade_id:
                    continue
                side = str(trade.get("Side", "")).strip().lower()
                trade_rows.append(
                    {
                        "TradeID": new_id("trd"),
                        "WriteBatchID": "",
                        "Timestamp": now_iso(),
                        "Date": reversal_date,
                        "User": user,
                        "AssetID": str(trade.get("AssetID", "")),
                        "Book": str(trade.get("Book", "")),
                        "Side": "sell" if side == "buy" else "buy",
                        "Quantity": trade.get("Quantity", 0),
                        "UnitPrice": trade.get("UnitPrice", 0),
                        "Fees": trade.get("Fees", 0),
                        "GrossAmount": trade.get("GrossAmount", 0),
                        "NetAmount": trade.get("NetAmount", 0),
                        "AccountID": str(trade.get("AccountID", "")),
                        "LedgerEntryID": reversal["EntryID"],
                        "RealizedGain": -as_int(trade.get("RealizedGain")),
                        "Notes": f"Reversal: {reason}",
                        "Status": "pending",
                        "ReversalOfTradeID": original_trade_id,
                    }
                )
                break
    if trade_rows:
        reversal["LinkedTradeID"] = trade_rows[0]["TradeID"]

    result = commit_batch(
        user,
        [reversal],
        trade_rows,
        audit_action="reverse_entry",
        audit_meta={"original_entry_id": entry_id_value, "reason": reason},
    )
    if trade_rows:
        try:
            from src.services.assets import rebuild_assets

            rebuild_assets(user)
        except Exception:
            pass
    return result
