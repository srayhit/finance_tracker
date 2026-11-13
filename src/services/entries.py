"""Application services that turn a validated form into ledger rows."""

from __future__ import annotations

from datetime import date

from src.data.lexicon import tag_id
from src.services.accounts import get_account
from src.services.categories import get_category
from src.services.ledger import (
    commit_batch,
    compute_balances,
    finalize_batch,
    find_by_client_request_id,
    new_ledger_row,
)
from src.services.tagging import MAX_TAGS, record_learning
from src.utils.ids import clean_text
from src.utils.privacy import sanitize_free_text


def validate_entry_date(entry_date: date | str) -> str:
    text = str(entry_date)[:10]
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        raise ValueError("Choose a valid date.")
    if parsed > date.today():
        raise ValueError("Future dates are not allowed for ledger entries.")
    return parsed.isoformat()


def _require_account(account_id: str, user: str) -> dict:
    account = get_account(account_id)
    if not account or str(account.get("User", "")).strip() != user:
        raise ValueError("Choose one of your accounts.")
    if str(account.get("IsActive", "TRUE")).strip().lower() in {"false", "0", "no"}:
        raise ValueError("That account is inactive.")
    return account


def _require_category(category_id_value: str, category_type: str) -> dict | None:
    if not category_id_value:
        return None
    category = get_category(category_id_value)
    if not category:
        raise ValueError("Choose a valid category.")
    if str(category.get("Type", "")).strip().lower() != category_type.strip().lower():
        raise ValueError(f"Category must be an {category_type} category.")
    return category


def _tag_list(tag_ids: list[str] | None, method: str = "") -> list[str]:
    values = [str(tag).strip() for tag in (tag_ids or []) if str(tag).strip()]
    if method:
        value = tag_id("method", method)
        if value and value not in values:
            values.append(value)
    return list(dict.fromkeys(values))[:MAX_TAGS]


def _already_saved(user: str, client_request_id: str) -> dict | None:
    if not client_request_id:
        return None
    row = find_by_client_request_id(user, client_request_id)
    if not row:
        return None
    batch_id = str(row.get("WriteBatchID", "")).strip()
    if batch_id and str(row.get("Status", "")).strip().lower() == "pending":
        try:
            finalize_batch(batch_id, user)
        except Exception:
            pass
    return {
        "entry_ids": [str(row.get("EntryID"))],
        "trade_ids": [],
        "batch_id": batch_id,
        "already_saved": True,
    }


def post_expense(
    user: str,
    entry_date: date | str,
    amount_paise: int,
    account_id: str,
    category_id_value: str,
    method: str,
    description: str = "",
    tag_ids: list[str] | None = None,
    is_private: bool = False,
    client_request_id: str = "",
    duplicate_of_entry_id: str = "",
) -> dict:
    existing = _already_saved(user, client_request_id)
    if existing:
        return existing
    entry_date = validate_entry_date(entry_date)
    amount = int(amount_paise or 0)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    _require_account(account_id, user)
    _require_category(category_id_value, "Expenditure")
    tags = _tag_list(tag_ids, method)
    row = new_ledger_row(
        user=user,
        entry_type="expense",
        entry_date=entry_date,
        amount_paise=amount,
        account_id=account_id,
        category_id=category_id_value,
        description=sanitize_free_text(description, 120),
        tag_ids=tags,
        is_private=is_private,
        client_request_id=client_request_id,
        duplicate_of_entry_id=duplicate_of_entry_id,
    )
    result = commit_batch(
        user,
        [row],
        audit_action="post_expense",
        audit_meta={"category_id": category_id_value, "method": method},
        default_method=method,
        source_account_id=account_id,
    )
    if description:
        try:
            record_learning(user, description, tags, category_id_value)
        except Exception:
            pass
    return result


def post_income(
    user: str,
    entry_date: date | str,
    amount_paise: int,
    account_id: str,
    category_id_value: str,
    description: str = "",
    payer: str = "",
    tax_withheld_paise: int = 0,
    tag_ids: list[str] | None = None,
    is_private: bool = False,
    client_request_id: str = "",
    duplicate_of_entry_id: str = "",
) -> dict:
    existing = _already_saved(user, client_request_id)
    if existing:
        return existing
    entry_date = validate_entry_date(entry_date)
    amount = int(amount_paise or 0)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    _require_account(account_id, user)
    _require_category(category_id_value, "Income")
    text = sanitize_free_text(description, 120)
    payer = sanitize_free_text(payer, 60)
    if payer and payer.lower() not in text.lower():
        text = f"{text} — {payer}".strip(" —")
    row = new_ledger_row(
        user=user,
        entry_type="income",
        entry_date=entry_date,
        amount_paise=amount,
        account_id=account_id,
        tax_withheld_paise=max(0, int(tax_withheld_paise or 0)),
        category_id=category_id_value,
        description=text,
        tag_ids=_tag_list(tag_ids),
        is_private=is_private,
        client_request_id=client_request_id,
        duplicate_of_entry_id=duplicate_of_entry_id,
    )
    return commit_batch(
        user,
        [row],
        audit_action="post_income",
        audit_meta={"category_id": category_id_value, "tds_information_only": int(tax_withheld_paise or 0)},
        default_method="netbanking",
        source_account_id=account_id,
    )


def post_transfer(
    user: str,
    entry_date: date | str,
    from_account_id: str,
    to_account_id: str,
    amount_paise: int,
    method: str = "netbanking",
    description: str = "",
    tag_ids: list[str] | None = None,
    is_private: bool = False,
    client_request_id: str = "",
    duplicate_of_entry_id: str = "",
    audit_action: str = "post_transfer",
) -> dict:
    existing = _already_saved(user, client_request_id)
    if existing:
        return existing
    entry_date = validate_entry_date(entry_date)
    amount = int(amount_paise or 0)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if str(from_account_id).strip() == str(to_account_id).strip():
        raise ValueError("From and to accounts must be different.")
    _require_account(from_account_id, user)
    _require_account(to_account_id, user)
    row = new_ledger_row(
        user=user,
        entry_type="transfer",
        entry_date=entry_date,
        amount_paise=amount,
        account_id=from_account_id,
        counter_account_id=to_account_id,
        description=sanitize_free_text(description, 120),
        tag_ids=_tag_list(tag_ids, method),
        is_private=is_private,
        client_request_id=client_request_id,
        duplicate_of_entry_id=duplicate_of_entry_id,
    )
    return commit_batch(
        user,
        [row],
        audit_action=audit_action,
        audit_meta={"from": from_account_id, "to": to_account_id, "method": method},
        default_method=method,
        source_account_id=from_account_id,
    )


def post_card_payment(
    user: str,
    entry_date: date | str,
    from_account_id: str,
    card_account_id: str,
    amount_paise: int,
    method: str = "netbanking",
    description: str = "",
    is_private: bool = False,
    client_request_id: str = "",
    duplicate_of_entry_id: str = "",
) -> dict:
    source = _require_account(from_account_id, user)
    card = _require_account(card_account_id, user)
    if str(source.get("Kind", "")).strip().lower() == "credit_card":
        raise ValueError("Pay a card from a bank, wallet or cash account.")
    if str(card.get("Kind", "")).strip().lower() != "credit_card":
        raise ValueError("The destination must be a credit card.")
    return post_transfer(
        user=user,
        entry_date=entry_date,
        from_account_id=from_account_id,
        to_account_id=card_account_id,
        amount_paise=amount_paise,
        method=method,
        description=description or f"Card payment — {card.get('Nickname', '')}",
        is_private=is_private,
        client_request_id=client_request_id,
        duplicate_of_entry_id=duplicate_of_entry_id,
        audit_action="card_payment",
    )


def post_adjustment(
    user: str,
    entry_date: date | str,
    account_id: str,
    actual_balance_paise: int,
    reason: str,
    note: str = "",
    client_request_id: str = "",
    duplicate_of_entry_id: str = "",
) -> dict:
    existing = _already_saved(user, client_request_id)
    if existing:
        return existing
    entry_date = validate_entry_date(entry_date)
    _require_account(account_id, user)
    computed = compute_balances(user, active_only=False).get(str(account_id), 0)
    actual = int(actual_balance_paise or 0)
    difference = actual - computed
    if difference == 0:
        raise ValueError("Actual balance already matches. Nothing to reconcile.")
    reason = clean_text(reason, 80)
    if not reason:
        raise ValueError("A reason is required.")
    description = sanitize_free_text(f"{reason}: {note}" if note else reason, 120)
    row = new_ledger_row(
        user=user,
        entry_type="adjustment",
        entry_date=entry_date,
        amount_paise=difference,
        account_id=account_id,
        description=description,
        client_request_id=client_request_id,
        duplicate_of_entry_id=duplicate_of_entry_id,
    )
    return commit_batch(
        user,
        [row],
        audit_action="reconcile",
        audit_meta={
            "computed_balance": computed,
            "actual_balance": actual,
            "difference": difference,
            "reason": reason,
        },
    )
