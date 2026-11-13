"""Add-entry experience: one compact form, one confirmation, one write."""

from __future__ import annotations

import functools
from datetime import date, timedelta

import streamlit as st

from src.data.lexicon import tag_id
from src.services.accounts import (
    account_label,
    account_map,
    account_options,
    cards,
    cash_accounts,
    create_account,
    find_nickname_duplicate,
    get_account,
    list_accounts,
)
from src.services.assets import (
    ASSET_TYPE_LABELS,
    FINANCIAL_TYPES,
    PHYSICAL_TYPES,
    asset_label,
    asset_options,
    get_asset,
    list_assets,
    record_buy,
    record_sell,
    update_valuation,
)
from src.services.categories import ensure_category, list_categories
from src.services.entries import (
    post_adjustment,
    post_card_payment,
    post_expense,
    post_income,
    post_transfer,
)
from src.services.ledger import (
    available_limit,
    compute_balances,
    find_near_duplicates,
    outstanding,
    reverse_entry,
)
from src.services.limits import PERIODS, SCOPES, save_limit
from src.services.recurring import FREQUENCIES, NOTIFY_CHANNELS, save_rule, upcoming_rules
from src.services.settings import resolve_default_account
from src.services.tagging import MAX_TAGS, suggest_tags, tag_name_map, tag_options
from src.ui.components import (
    account_name,
    candidate_html,
    due_strip,
    empty_state,
    money,
    page_header,
    stats_grid,
    summary,
)
from src.utils.ids import as_int, new_id
from src.utils.money import from_paise, to_paise
from src.utils.privacy import sanitize_free_text

ENTRY_OPTIONS = [
    ("Expense", "expense"),
    ("Income", "income"),
    ("Transfer", "transfer"),
    ("Card payment", "card_payment"),
    ("Stock buy", "stock_buy"),
    ("Stock sell", "stock_sell"),
    ("Asset buy", "asset_buy"),
    ("Asset sell", "asset_sell"),
    ("Reconcile", "reconcile"),
    ("New account", "account"),
    ("New card", "card"),
    ("Limit", "limit"),
    ("Bill", "bill"),
]
LABEL_TO_KIND = {label: kind for label, kind in ENTRY_OPTIONS}
KIND_TO_LABEL = {kind: label for label, kind in ENTRY_OPTIONS}

METHOD_OPTIONS = [
    ("upi", "UPI"),
    ("netbanking", "Net banking"),
    ("auto_debit", "Auto debit"),
    ("cheque", "Cheque"),
    ("cash", "Cash"),
    ("card", "Card"),
    ("wallet", "Wallet"),
]
METHOD_LABELS = dict(METHOD_OPTIONS)
CARD_PAY_METHODS = [
    ("netbanking", "Net banking"),
    ("upi", "UPI"),
    ("auto_debit", "Auto debit"),
    ("cheque", "Cheque"),
]
INCOME_CATEGORY_HINT = {
    "Salary": "Net amount credited",
    "Interest": "Bank / FD credit",
    "Dividend": "Company payout",
    "Rental": "Property income",
    "Freelance": "Client payment",
    "Gift": "Gift or refund",
    "Refund": "Money returned",
    "Other": "Anything else",
}


# ---------------------------------------------------------------------------
# session helpers
# ---------------------------------------------------------------------------
def _ver(kind: str) -> int:
    return int(st.session_state.get(f"formver_{kind}", 0))


def _bump(kind: str) -> None:
    st.session_state[f"formver_{kind}"] = _ver(kind) + 1


def _req(kind: str) -> str:
    key = f"req_{kind}_{_ver(kind)}"
    if key not in st.session_state:
        st.session_state[key] = new_id("req")
    return st.session_state[key]


def _clear_pending(kind: str) -> None:
    st.session_state.pop("pending_plan", None)
    st.session_state.pop(f"req_{kind}_{_ver(kind)}", None)


def _has_pending() -> bool:
    return bool(st.session_state.get("pending_plan"))


def _candidate_entry_id(candidate: dict) -> str:
    row = candidate.get("row", {})
    return str(row.get("LedgerEntryID") or row.get("EntryID") or row.get("TradeID") or "")


def _queue(
    kind: str,
    kwargs: dict,
    summary_rows: list[tuple[str, str]],
    candidates: list[dict] | None = None,
    warnings: list[str] | None = None,
) -> None:
    candidates = candidates or []
    st.session_state["pending_plan"] = {
        "kind": kind,
        "kwargs": kwargs,
        "summary": summary_rows,
        "candidates": candidates,
        "warnings": warnings or [],
        "duplicate_of": _candidate_entry_id(candidates[0]) if candidates else "",
    }
    st.rerun()


def queue_plan(
    kind: str,
    kwargs: dict,
    summary_rows: list[tuple[str, str]],
    candidates: list[dict] | None = None,
    warnings: list[str] | None = None,
) -> None:
    """Queue any entry (including reversal/valuation) for the global confirm screen."""
    _queue(kind, kwargs, summary_rows, candidates, warnings)


def execute_plan(user: str, plan: dict, allow_duplicate: bool = False):
    kind = plan["kind"]
    kwargs = dict(plan["kwargs"])
    duplicate = plan.get("duplicate_of", "") if allow_duplicate else ""
    if duplicate and kind in {
        "expense",
        "income",
        "transfer",
        "card_payment",
        "stock_buy",
        "stock_sell",
        "asset_buy",
        "asset_sell",
    }:
        kwargs["duplicate_of_entry_id"] = duplicate
    if kind == "expense":
        return post_expense(**kwargs)
    if kind == "income":
        return post_income(**kwargs)
    if kind == "transfer":
        return post_transfer(**kwargs)
    if kind == "card_payment":
        return post_card_payment(**kwargs)
    if kind == "stock_buy":
        return record_buy(**kwargs)
    if kind == "stock_sell":
        return record_sell(**kwargs)
    if kind == "asset_buy":
        valuation_price = int(kwargs.pop("valuation_price_paise", 0) or 0)
        result = record_buy(**kwargs)
        if valuation_price > 0 and result.get("asset_id"):
            try:
                update_valuation(user, result["asset_id"], valuation_price)
            except Exception as exc:
                result["asset_warning"] = f"Trade saved; valuation not updated: {exc}"
        return result
    if kind == "asset_sell":
        return record_sell(**kwargs)
    if kind == "reconcile":
        return post_adjustment(**kwargs)
    if kind == "account":
        kwargs["allow_duplicate"] = bool(plan.get("candidates"))
        return create_account(**kwargs)
    if kind == "card":
        kwargs["allow_duplicate"] = bool(plan.get("candidates"))
        return create_account(**kwargs)
    if kind == "limit":
        return save_limit(**kwargs)
    if kind == "bill":
        return save_rule(**kwargs)
    if kind == "valuation":
        return update_valuation(**kwargs)
    if kind == "reversal":
        return reverse_entry(**kwargs)
    raise ValueError("Unknown entry type.")


def render_pending_confirmation(user: str) -> bool:
    plan = st.session_state.get("pending_plan")
    if not plan:
        return False
    kind = plan["kind"]
    plan_user = str(plan.get("kwargs", {}).get("user", "") or user)
    page_header("Confirm", "Nothing is written until you press save.", "final check")
    summary(plan["summary"])
    for warning in plan.get("warnings", []):
        st.warning(warning)
    if plan.get("candidates"):
        st.warning("Possible duplicate found. Review it before saving again.")
        lookup = account_map(plan_user, active_only=False)
        for candidate in plan["candidates"]:
            st.markdown(candidate_html(candidate, lookup), unsafe_allow_html=True)
    cols = st.columns([1, 1, 2.2])
    if cols[0].button("Cancel", key=f"pending_cancel_{kind}", width="stretch"):
        _clear_pending(kind)
        st.rerun()
    label = "Save anyway" if plan.get("candidates") else "Confirm & save"
    if cols[1].button(
        label, type="primary", key=f"pending_confirm_{kind}", width="stretch"
    ):
        try:
            result = execute_plan(plan_user, plan, allow_duplicate=bool(plan.get("candidates")))
            if isinstance(result, dict) and result.get("already_saved"):
                st.toast("Already saved — no duplicate written.", icon="✅")
            else:
                st.toast("Saved to the ledger.", icon="✅")
            if isinstance(result, dict) and result.get("asset_warning"):
                st.warning(result["asset_warning"])
        except Exception as exc:
            st.error(str(exc))
            return True
        _clear_pending(kind)
        _bump(kind)
        st.rerun()
    return True


# ---------------------------------------------------------------------------
# reusable field helpers
# ---------------------------------------------------------------------------
def _account_select(
    label: str,
    rows: list[dict],
    key: str,
    default_id: str = "",
    on_change=None,
) -> str:
    if not rows:
        return ""
    labels = {account_label(row): str(row.get("AccountID")) for row in rows}
    options = list(labels)
    current = st.session_state.get(key)
    if current not in labels:
        default_label = next(
            (label_text for label_text, account_id in labels.items() if account_id == default_id),
            options[0],
        )
        st.session_state[key] = default_label
    chosen = st.selectbox(
        label,
        options=options,
        key=key,
        on_change=on_change,
    )
    return labels.get(chosen, "")


def _category_select(
    label: str,
    category_type: str,
    key: str,
    suggested_id: str = "",
) -> str:
    categories = list_categories(category_type)
    if not categories:
        st.warning(f"No {category_type} categories found. Add one below.")
        return ""
    ids = [str(row.get("CategoryID")) for row in categories]
    names = {str(row.get("CategoryID")): str(row.get("Category")) for row in categories}
    current = st.session_state.get(key)
    if current not in ids:
        st.session_state[key] = suggested_id if suggested_id in ids else ids[0]
    return st.selectbox(label, options=ids, format_func=lambda value: names.get(value, value), key=key)


def _tag_select(user: str, key: str, suggested: list[str]) -> list[str]:
    ids, labels = tag_options(user)
    if not ids:
        return []
    current = st.session_state.get(key)
    if current is None:
        st.session_state[key] = [value for value in suggested if value in ids][:MAX_TAGS]
    return st.multiselect(
        "Tags",
        options=ids,
        format_func=lambda value: labels.get(value, value),
        key=key,
        max_selections=MAX_TAGS,
        help="Suggested from the description. Remove any chip before saving.",
    )


def _inline_new_category(category_type: str, prefix: str) -> None:
    with st.expander("＋ New category"):
        name = st.text_input("Category name", key=f"{prefix}_newcat")
        if st.button("Add category", key=f"{prefix}_addcat"):
            try:
                ensure_category(name, category_type)
                st.toast("Category added.", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _suggest_callback(user: str, prefix: str) -> None:
    description = st.session_state.get(f"{prefix}_desc", "")
    method = st.session_state.get(f"{prefix}_method", "")
    suggestion = suggest_tags(description, user, method=method)
    st.session_state[f"{prefix}_tags"] = suggestion.tag_ids
    if suggestion.category_id:
        st.session_state[f"{prefix}_cat"] = suggestion.category_id


def _account_changed(user: str, prefix: str, labels_to_ids: dict[str, str]) -> None:
    label = st.session_state.get(f"{prefix}_account", "")
    account = get_account(labels_to_ids.get(label, ""))
    if not account:
        return
    kind = str(account.get("Kind", "")).strip().lower()
    method = "card" if kind == "credit_card" else "cash" if kind == "cash" else "wallet" if kind == "wallet" else "upi"
    st.session_state[f"{prefix}_method"] = method
    _suggest_callback(user, prefix)


def _method_select(key: str, default: str = "upi", options: list[tuple[str, str]] | None = None, on_change=None) -> str:
    options = options or METHOD_OPTIONS
    values = [value for value, _ in options]
    labels = dict(options)
    current = st.session_state.get(key)
    if current not in values:
        st.session_state[key] = default if default in values else values[0]
    return st.selectbox(
        "Method",
        options=values,
        format_func=lambda value: labels.get(value, value),
        key=key,
        on_change=on_change,
    )


def _amount_input(label: str, key: str, default_paise: int = 0, min_value: float = 0.0) -> int:
    current = st.session_state.get(key)
    if current is None:
        st.session_state[key] = from_paise(default_paise)
    value = st.number_input(
        label,
        min_value=min_value,
        step=100.0,
        format="%.2f",
        key=key,
    )
    return to_paise(value)


def _sync_buy_price(user: str, prefix: str, labels: dict[str, str]) -> None:
    asset = get_asset(labels.get(st.session_state.get(f"{prefix}_holding", ""), ""), user)
    if asset:
        st.session_state[f"{prefix}_price"] = from_paise(as_int(asset.get("CurrentPrice")))


def _sync_sell_defaults(user: str, prefix: str, labels: dict[str, str]) -> None:
    asset = get_asset(labels.get(st.session_state.get(f"{prefix}_asset", ""), ""), user)
    if not asset:
        return
    held = float(asset.get("Quantity") or 0)
    st.session_state[f"{prefix}_qty"] = held
    st.session_state[f"{prefix}_proceeds"] = from_paise(
        int(round(held * as_int(asset.get("CurrentPrice"))))
    )


def _tag_names(user: str) -> dict[str, str]:
    return tag_name_map(user)


def _summary_account(account_id_value: str) -> str:
    account = get_account(account_id_value)
    return account_label(account) if account else "—"


# ---------------------------------------------------------------------------
# expense
# ---------------------------------------------------------------------------
def _expense_form(user: str) -> None:
    kind = "expense"
    prefix = f"exp_{_ver(kind)}"
    rows = list_accounts(user, active_only=True)
    if not rows:
        empty_state("Add a bank, wallet or card account first.")
        return
    labels_to_ids = {account_label(row): str(row.get("AccountID")) for row in rows}
    default_account = resolve_default_account(user, "upi")
    default_id = str(default_account.get("AccountID")) if default_account else ""

    c1, c2, c3 = st.columns([1, 1, 1.25])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    amount = c2.number_input("Amount (₹)", min_value=0.0, step=100.0, format="%.2f", key=f"{prefix}_amount")
    with c3:
        account_id = _account_select(
            "Paid from",
            rows,
            f"{prefix}_account",
            default_id=default_id,
            on_change=functools.partial(_account_changed, user, prefix, labels_to_ids),
        )
    account = get_account(account_id)

    c4, c5, c6, c7 = st.columns([0.95, 2.1, 1.15, 0.6])
    with c4:
        method = _method_select(
            f"{prefix}_method",
            default="card" if str(account.get("Kind", "")).strip().lower() == "credit_card" else "upi",
            on_change=functools.partial(_suggest_callback, user, prefix),
        )
    with c5:
        desc = st.text_input(
            "Description",
            key=f"{prefix}_desc",
            placeholder="e.g. apples, milk from blinkit",
            on_change=functools.partial(_suggest_callback, user, prefix),
        )
    suggestion = suggest_tags(desc or "", user, method=method)
    with c6:
        category_id_value = _category_select(
            "Category", "Expenditure", f"{prefix}_cat", suggestion.category_id
        )
    with c7:
        is_private = st.checkbox("Private", key=f"{prefix}_private")
    if suggestion.category_name:
        st.caption(f"Category suggested from description: {suggestion.category_name}")
    tags = _tag_select(user, f"{prefix}_tags", suggestion.tag_ids)
    _inline_new_category("Expenditure", prefix)

    if st.button("Review entry", type="primary", key=f"{prefix}_review"):
        if amount <= 0:
            st.error("Amount must be greater than zero.")
            return
        warnings = []
        if account and str(account.get("Kind", "")).strip().lower() == "credit_card":
            balances = compute_balances(user, active_only=False)
            limit = as_int(account.get("CreditLimit"))
            current = outstanding(account, balances.get(account_id, 0))
            if limit and (current + to_paise(amount)) / limit * 100 >= 80:
                warnings.append("This expense pushes card utilization above 80%.")
        candidates = find_near_duplicates(
            user,
            "expense",
            entry_date,
            to_paise(amount),
            account_id=account_id,
            description=desc or "",
        )
        kwargs = {
            "user": user,
            "entry_date": entry_date,
            "amount_paise": to_paise(amount),
            "account_id": account_id,
            "category_id_value": category_id_value,
            "method": method,
            "description": desc or "",
            "tag_ids": tags,
            "is_private": is_private,
            "client_request_id": _req(kind),
        }
        names = _tag_names(user)
        _queue(
            kind,
            kwargs,
            [
                ("Date", str(entry_date)),
                ("Amount", money(to_paise(amount))),
                ("Paid from", _summary_account(account_id)),
                ("Method", METHOD_LABELS.get(method, method)),
                ("Category", next((r["Category"] for r in list_categories("Expenditure") if r["CategoryID"] == category_id_value), "—")),
                ("Tags", ", ".join(names.get(value, value) for value in tags) or "—"),
                ("Description", desc or "—"),
                ("Private", "Yes" if is_private else "No"),
            ],
            candidates,
            warnings,
        )


# ---------------------------------------------------------------------------
# income
# ---------------------------------------------------------------------------
def _income_form(user: str) -> None:
    kind = "income"
    prefix = f"inc_{_ver(kind)}"
    rows = list_accounts(user, active_only=True)
    if not rows:
        empty_state("Add an account first.")
        return
    labels_to_ids = {account_label(row): str(row.get("AccountID")) for row in rows}
    default_account = resolve_default_account(user, "netbanking")
    default_id = str(default_account.get("AccountID")) if default_account else ""

    c1, c2, c3 = st.columns([1, 1, 1.25])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    amount = c2.number_input("Net amount (₹)", min_value=0.0, step=100.0, format="%.2f", key=f"{prefix}_amount")
    with c3:
        account_id = _account_select("Received in", rows, f"{prefix}_account", default_id=default_id)
    c4, c5, c6 = st.columns([1.1, 1.4, 1])
    with c4:
        category_id_value = _category_select("Income category", "Income", f"{prefix}_cat", "")
    payer = c5.text_input("Source / payer", key=f"{prefix}_payer", placeholder="Employer, bank, client")
    tax = c6.number_input(
        "TDS withheld (₹, info only)", min_value=0.0, step=100.0, format="%.2f", key=f"{prefix}_tax"
    )
    desc = st.text_input("Description", key=f"{prefix}_desc", placeholder="Optional note")
    is_private = st.checkbox("Private", key=f"{prefix}_private")

    if st.button("Review entry", type="primary", key=f"{prefix}_review"):
        if amount <= 0:
            st.error("Amount must be greater than zero.")
            return
        candidates = find_near_duplicates(
            user, "income", entry_date, to_paise(amount), account_id=account_id, description=desc or ""
        )
        kwargs = {
            "user": user,
            "entry_date": entry_date,
            "amount_paise": to_paise(amount),
            "account_id": account_id,
            "category_id_value": category_id_value,
            "description": desc or "",
            "payer": payer or "",
            "tax_withheld_paise": to_paise(tax),
            "is_private": is_private,
            "client_request_id": _req(kind),
        }
        _queue(
            kind,
            kwargs,
            [
                ("Date", str(entry_date)),
                ("Net amount", money(to_paise(amount))),
                ("Received in", _summary_account(account_id)),
                ("Category", next((r["Category"] for r in list_categories("Income") if r["CategoryID"] == category_id_value), "—")),
                ("Source", payer or "—"),
                ("TDS", f"{money(to_paise(tax))} (information only)"),
                ("Description", desc or "—"),
                ("Private", "Yes" if is_private else "No"),
            ],
            candidates,
        )


# ---------------------------------------------------------------------------
# transfer and card payment
# ---------------------------------------------------------------------------
def _transfer_form(user: str) -> None:
    kind = "transfer"
    prefix = f"trf_{_ver(kind)}"
    rows = list_accounts(user, active_only=True)
    if len(rows) < 2:
        empty_state("Add at least two accounts to transfer between.")
        return
    labels_to_ids = {account_label(row): str(row.get("AccountID")) for row in rows}
    default_from = resolve_default_account(user, "netbanking")
    from_id = str(default_from.get("AccountID")) if default_from else ""
    c1, c2, c3 = st.columns([1, 1, 1.25])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    amount = c2.number_input("Amount (₹)", min_value=0.0, step=100.0, format="%.2f", key=f"{prefix}_amount")
    from_account = _account_select("From account", rows, f"{prefix}_from", default_id=from_id)
    to_account = _account_select("To account", rows, f"{prefix}_to", default_id=rows[1].get("AccountID"))
    c4, c5 = st.columns([1, 1])
    method = _method_select(f"{prefix}_method", default="netbanking")
    desc = c4.text_input("Note", key=f"{prefix}_desc")
    is_private = c5.checkbox("Private", key=f"{prefix}_private")

    if st.button("Review entry", type="primary", key=f"{prefix}_review"):
        if amount <= 0:
            st.error("Amount must be greater than zero.")
            return
        if from_account == to_account:
            st.error("From and to accounts must be different.")
            return
        candidates = find_near_duplicates(
            user,
            "transfer",
            entry_date,
            to_paise(amount),
            account_id=from_account,
            counter_account_id=to_account,
        )
        kwargs = {
            "user": user,
            "entry_date": entry_date,
            "from_account_id": from_account,
            "to_account_id": to_account,
            "amount_paise": to_paise(amount),
            "method": method,
            "description": desc or "",
            "is_private": is_private,
            "client_request_id": _req(kind),
        }
        _queue(
            kind,
            kwargs,
            [
                ("Date", str(entry_date)),
                ("Amount", money(to_paise(amount))),
                ("From", _summary_account(from_account)),
                ("To", _summary_account(to_account)),
                ("Method", METHOD_LABELS.get(method, method)),
                ("Note", desc or "—"),
                ("Private", "Yes" if is_private else "No"),
            ],
            candidates,
        )


def _card_payment_form(user: str) -> None:
    kind = "card_payment"
    prefix = f"cp_{_ver(kind)}"
    cash_rows = cash_accounts(user)
    card_rows = cards(user)
    if not cash_rows or not card_rows:
        empty_state("Add a bank/wallet account and a credit card first.")
        return
    cash_labels = {account_label(row): str(row.get("AccountID")) for row in cash_rows}
    card_labels = {account_label(row): str(row.get("AccountID")) for row in card_rows}
    default_cash = resolve_default_account(user, "bill_payment")
    default_cash_id = str(default_cash.get("AccountID")) if default_cash else ""
    balances = compute_balances(user, active_only=False)
    first_card = card_rows[0]
    first_outstanding = outstanding(first_card, balances.get(str(first_card.get("AccountID")), 0))

    c1, c2 = st.columns([1, 1.2])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    with c2:
        card_label = st.selectbox("Card", options=list(card_labels), key=f"{prefix}_card")
    card_id = card_labels.get(card_label, "")
    card = get_account(card_id)
    card_out = outstanding(card, balances.get(card_id, 0)) if card else 0
    if f"{prefix}_amount" not in st.session_state:
        st.session_state[f"{prefix}_amount"] = from_paise(first_outstanding or card_out)
    c3, c4 = st.columns([1, 1])
    amount = c3.number_input("Amount (₹)", min_value=0.0, step=100.0, format="%.2f", key=f"{prefix}_amount")
    with c4:
        from_account = _account_select("Pay from", cash_rows, f"{prefix}_from", default_id=default_cash_id)
    method = _method_select(f"{prefix}_method", default="netbanking", options=CARD_PAY_METHODS)
    st.caption(f"Current outstanding on selected card: {money(card_out)}")
    desc = st.text_input("Note", key=f"{prefix}_desc")
    is_private = st.checkbox("Private", key=f"{prefix}_private")

    if st.button("Review entry", type="primary", key=f"{prefix}_review"):
        if amount <= 0:
            st.error("Amount must be greater than zero.")
            return
        candidates = find_near_duplicates(
            user,
            "card_payment",
            entry_date,
            to_paise(amount),
            account_id=from_account,
            counter_account_id=card_id,
        )
        kwargs = {
            "user": user,
            "entry_date": entry_date,
            "from_account_id": from_account,
            "card_account_id": card_id,
            "amount_paise": to_paise(amount),
            "method": method,
            "description": desc or "",
            "is_private": is_private,
            "client_request_id": _req(kind),
        }
        _queue(
            kind,
            kwargs,
            [
                ("Date", str(entry_date)),
                ("Amount", money(to_paise(amount))),
                ("Pay from", _summary_account(from_account)),
                ("Card", _summary_account(card_id)),
                ("Outstanding before", money(card_out)),
                ("Outstanding after", money(max(0, card_out - to_paise(amount)))),
                ("Method", METHOD_LABELS.get(method, method)),
                ("Note", desc or "—"),
            ],
            candidates,
        )


# ---------------------------------------------------------------------------
# stock buy / sell
# ---------------------------------------------------------------------------
def _stock_buy_form(user: str) -> None:
    kind = "stock_buy"
    prefix = f"sb_{_ver(kind)}"
    rows = list_accounts(user, active_only=True)
    if not rows:
        empty_state("Add a brokerage, bank or wallet account first.")
        return
    default_account = resolve_default_account(user, "netbanking")
    default_id = str(default_account.get("AccountID")) if default_account else ""
    holdings = list_assets(user, book="investment", active_only=True)
    holding_labels = {"New holding": ""}
    holding_labels.update({asset_label(row): str(row.get("AssetID")) for row in holdings})

    c1, c2 = st.columns([1, 1])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    with c2:
        account_id = _account_select("Paid from", rows, f"{prefix}_account", default_id=default_id)
    existing_label = st.selectbox(
        "Holding",
        options=list(holding_labels),
        key=f"{prefix}_holding",
        on_change=functools.partial(_sync_buy_price, user, prefix, holding_labels),
    )
    existing_id = holding_labels.get(existing_label, "")
    existing = get_asset(existing_id, user) if existing_id else None

    if existing:
        asset_type = str(existing.get("AssetType", "equity"))
        name = str(existing.get("Name", ""))
        symbol = str(existing.get("Symbol", ""))
        unit = str(existing.get("Unit", "units"))
        st.caption(
            f"{asset_label(existing)} · held {float(existing.get('Quantity') or 0):g} {unit} · "
            f"avg cost {money(existing.get('AvgCost'))}"
        )
    else:
        c3, c4 = st.columns([1, 1])
        asset_type = c3.selectbox(
            "Asset type",
            options=FINANCIAL_TYPES,
            format_func=lambda value: ASSET_TYPE_LABELS.get(value, value),
            key=f"{prefix}_type",
        )
        name = c4.text_input("Asset name", key=f"{prefix}_name", placeholder="NIFTY 50 ETF")
        c5, c6 = st.columns([1, 1])
        symbol = c5.text_input("Symbol", key=f"{prefix}_symbol", placeholder="NIFTYBEES")
        unit = c6.text_input("Unit", value="units", key=f"{prefix}_unit")
    c7, c8, c9 = st.columns([1, 1, 1])
    quantity = c7.number_input("Quantity", min_value=0.0, step=1.0, format="%.4f", key=f"{prefix}_qty")
    default_price = as_int(existing.get("CurrentPrice")) if existing else 0
    unit_price = _amount_input("Unit price (₹)", f"{prefix}_price", default_paise=default_price)
    fees = _amount_input("Fees (₹)", f"{prefix}_fees")
    notes = st.text_input("Notes", key=f"{prefix}_notes")
    is_private = st.checkbox("Private ledger entry", key=f"{prefix}_private")

    if st.button("Review entry", type="primary", key=f"{prefix}_review"):
        if quantity <= 0:
            st.error("Quantity must be greater than zero.")
            return
        if unit_price <= 0:
            st.error("Unit price must be greater than zero.")
            return
        if not existing and not name.strip():
            st.error("Asset name is required.")
            return
        gross = int(round(quantity * unit_price))
        total = gross + fees
        candidates = find_near_duplicates(
            user,
            "stock_buy",
            entry_date,
            total,
            account_id=account_id,
            asset_id=existing_id,
            quantity=quantity,
            unit_price=unit_price,
        )
        kwargs = {
            "user": user,
            "entry_date": entry_date,
            "account_id": account_id,
            "asset_type": asset_type,
            "name": name,
            "quantity": quantity,
            "unit_price_paise": unit_price,
            "fees_paise": fees,
            "symbol": symbol,
            "unit": unit,
            "notes": notes or "",
            "is_private": is_private,
            "client_request_id": _req(kind),
            "existing_asset_id": existing_id,
        }
        _queue(
            kind,
            kwargs,
            [
                ("Date", str(entry_date)),
                ("Holding", existing_label),
                ("Quantity", f"{quantity:g}"),
                ("Unit price", money(unit_price)),
                ("Gross", money(gross)),
                ("Fees", money(fees)),
                ("Cash out", money(total)),
                ("Paid from", _summary_account(account_id)),
                ("Notes", notes or "—"),
            ],
            candidates,
        )


def _stock_sell_form(user: str) -> None:
    kind = "stock_sell"
    prefix = f"ss_{_ver(kind)}"
    holdings = list_assets(user, book="investment", active_only=True)
    if not holdings:
        empty_state("No active stock / mutual fund holdings yet.")
        return
    labels = {asset_label(row): str(row.get("AssetID")) for row in holdings}
    c1, c2 = st.columns([1, 1.2])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    with c2:
        chosen = st.selectbox(
            "Holding",
            options=list(labels),
            key=f"{prefix}_asset",
            on_change=functools.partial(_sync_sell_defaults, user, prefix, labels),
        )
    asset = get_asset(labels.get(chosen, ""), user)
    held = float(asset.get("Quantity") or 0)
    unit = str(asset.get("Unit", "units"))
    st.caption(
        f"Held {held:g} {unit} · avg cost {money(asset.get('AvgCost'))} · "
        f"current {money(asset.get('CurrentPrice'))} per unit"
    )
    c3, c4, c5 = st.columns([1, 1, 1])
    quantity = c3.number_input(
        "Quantity sold",
        min_value=0.0,
        max_value=float(held) if held else 0.0,
        value=float(held) if held else 0.0,
        step=1.0,
        format="%.4f",
        key=f"{prefix}_qty",
    )
    default_proceeds = int(round(held * as_int(asset.get("CurrentPrice"))))
    proceeds = _amount_input("Total proceeds (₹)", f"{prefix}_proceeds", default_paise=default_proceeds)
    fees = _amount_input("Fees (₹)", f"{prefix}_fees")
    rows = list_accounts(user, active_only=True)
    default_account = resolve_default_account(user, "netbanking")
    account_id = _account_select(
        "Received in",
        rows,
        f"{prefix}_account",
        default_id=str(default_account.get("AccountID")) if default_account else "",
    )
    notes = st.text_input("Notes", key=f"{prefix}_notes")
    is_private = st.checkbox("Private ledger entry", key=f"{prefix}_private")

    if st.button("Review entry", type="primary", key=f"{prefix}_review"):
        if quantity <= 0:
            st.error("Quantity sold must be greater than zero.")
            return
        if quantity > held + 1e-6:
            st.error(f"Only {held:g} {unit} are held.")
            return
        if proceeds <= 0:
            st.error("Sale proceeds must be greater than zero.")
            return
        net = max(0, proceeds - fees)
        cost_basis = int(round(as_int(asset.get("AvgCost")) * quantity))
        realized = net - cost_basis
        candidates = find_near_duplicates(
            user,
            "stock_sell",
            entry_date,
            net,
            account_id=account_id,
            asset_id=str(asset.get("AssetID")),
            quantity=quantity,
            unit_price=int(round(proceeds / quantity)) if quantity else 0,
        )
        kwargs = {
            "user": user,
            "entry_date": entry_date,
            "asset_id": str(asset.get("AssetID")),
            "quantity": quantity,
            "total_proceeds_paise": proceeds,
            "account_id": account_id,
            "fees_paise": fees,
            "notes": notes or "",
            "is_private": is_private,
            "client_request_id": _req(kind),
        }
        _queue(
            kind,
            kwargs,
            [
                ("Date", str(entry_date)),
                ("Holding", chosen),
                ("Quantity sold", f"{quantity:g} {unit}"),
                ("Proceeds", money(proceeds)),
                ("Fees", money(fees)),
                ("Net received", money(net)),
                ("Cost basis", money(cost_basis)),
                ("Realized gain", money(realized, signed=True)),
                ("Received in", _summary_account(account_id)),
            ],
            candidates,
        )


# ---------------------------------------------------------------------------
# physical asset buy / sell
# ---------------------------------------------------------------------------
def _asset_buy_form(user: str) -> None:
    kind = "asset_buy"
    prefix = f"ab_{_ver(kind)}"
    rows = list_accounts(user, active_only=True)
    if not rows:
        empty_state("Add a bank/wallet account first.")
        return
    default_account = resolve_default_account(user, "netbanking")
    c1, c2, c3 = st.columns([1, 1, 1.2])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    asset_type = c2.selectbox(
        "Asset type",
        options=PHYSICAL_TYPES,
        format_func=lambda value: ASSET_TYPE_LABELS.get(value, value),
        key=f"{prefix}_type",
    )
    name = c3.text_input("Asset name", key=f"{prefix}_name", placeholder="Flat 302, gold 50g")
    c4, c5, c6 = st.columns([1, 1, 1.2])
    quantity = c4.number_input("Quantity", min_value=0.0, value=1.0, step=1.0, format="%.4f", key=f"{prefix}_qty")
    unit = c5.text_input("Unit", value="unit", key=f"{prefix}_unit")
    account_id = _account_select(
        "Paid from",
        rows,
        f"{prefix}_account",
        default_id=str(default_account.get("AccountID")) if default_account else "",
    )
    c7, c8, c9 = st.columns([1, 1, 1])
    purchase = _amount_input("Purchase price (₹, total)", f"{prefix}_purchase")
    fees = _amount_input("Fees / registration (₹)", f"{prefix}_fees")
    current_value = _amount_input("Current estimated value (₹)", f"{prefix}_current")
    notes = st.text_input("Notes", key=f"{prefix}_notes")
    is_private = st.checkbox("Private ledger entry", key=f"{prefix}_private")

    if st.button("Review entry", type="primary", key=f"{prefix}_review"):
        if quantity <= 0:
            st.error("Quantity must be greater than zero.")
            return
        if purchase <= 0:
            st.error("Purchase price must be greater than zero.")
            return
        if not name.strip():
            st.error("Asset name is required.")
            return
        unit_price = int(round(purchase / quantity))
        total = purchase + fees
        valuation_price = int(round(current_value / quantity)) if current_value > 0 else 0
        candidates = find_near_duplicates(
            user,
            "asset_purchase",
            entry_date,
            total,
            account_id=account_id,
            quantity=quantity,
            unit_price=unit_price,
        )
        kwargs = {
            "user": user,
            "entry_date": entry_date,
            "account_id": account_id,
            "asset_type": asset_type,
            "name": name,
            "quantity": quantity,
            "unit_price_paise": unit_price,
            "fees_paise": fees,
            "unit": unit,
            "notes": notes or "",
            "is_private": is_private,
            "client_request_id": _req(kind),
            "valuation_price_paise": valuation_price,
        }
        _queue(
            kind,
            kwargs,
            [
                ("Date", str(entry_date)),
                ("Asset", f"{name} · {ASSET_TYPE_LABELS.get(asset_type, asset_type)}"),
                ("Quantity", f"{quantity:g} {unit}"),
                ("Purchase price", money(purchase)),
                ("Fees", money(fees)),
                ("Cash out", money(total)),
                ("Unit cost", money(unit_price)),
                ("Current value", money(current_value) if current_value else "Acquisition cost"),
                ("Paid from", _summary_account(account_id)),
            ],
            candidates,
        )


def _asset_sell_form(user: str) -> None:
    kind = "asset_sell"
    prefix = f"as_{_ver(kind)}"
    holdings = list_assets(user, book="physical", active_only=True)
    if not holdings:
        empty_state("No active physical assets yet.")
        return
    labels = {asset_label(row): str(row.get("AssetID")) for row in holdings}
    c1, c2 = st.columns([1, 1.2])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    with c2:
        chosen = st.selectbox(
            "Asset",
            options=list(labels),
            key=f"{prefix}_asset",
            on_change=functools.partial(_sync_sell_defaults, user, prefix, labels),
        )
    asset = get_asset(labels.get(chosen, ""), user)
    held = float(asset.get("Quantity") or 0)
    unit = str(asset.get("Unit", "unit"))
    st.caption(f"Held {held:g} {unit} · avg cost {money(asset.get('AvgCost'))}")
    c3, c4, c5 = st.columns([1, 1, 1])
    quantity = c3.number_input(
        "Quantity sold",
        min_value=0.0,
        max_value=float(held) if held else 0.0,
        value=float(held) if held else 0.0,
        step=0.01,
        format="%.4f",
        key=f"{prefix}_qty",
    )
    proceeds = _amount_input("Sale proceeds (₹)", f"{prefix}_proceeds")
    fees = _amount_input("Fees / commission (₹)", f"{prefix}_fees")
    rows = list_accounts(user, active_only=True)
    default_account = resolve_default_account(user, "netbanking")
    account_id = _account_select(
        "Received in",
        rows,
        f"{prefix}_account",
        default_id=str(default_account.get("AccountID")) if default_account else "",
    )
    notes = st.text_input("Notes", key=f"{prefix}_notes")
    is_private = st.checkbox("Private ledger entry", key=f"{prefix}_private")

    if st.button("Review entry", type="primary", key=f"{prefix}_review"):
        if quantity <= 0:
            st.error("Quantity sold must be greater than zero.")
            return
        if quantity > held + 1e-6:
            st.error(f"Only {held:g} {unit} are held.")
            return
        if proceeds <= 0:
            st.error("Sale proceeds must be greater than zero.")
            return
        net = max(0, proceeds - fees)
        cost_basis = int(round(as_int(asset.get("AvgCost")) * quantity))
        realized = net - cost_basis
        candidates = find_near_duplicates(
            user,
            "asset_sale",
            entry_date,
            net,
            account_id=account_id,
            asset_id=str(asset.get("AssetID")),
            quantity=quantity,
            unit_price=int(round(proceeds / quantity)) if quantity else 0,
        )
        kwargs = {
            "user": user,
            "entry_date": entry_date,
            "asset_id": str(asset.get("AssetID")),
            "quantity": quantity,
            "total_proceeds_paise": proceeds,
            "account_id": account_id,
            "fees_paise": fees,
            "notes": notes or "",
            "is_private": is_private,
            "client_request_id": _req(kind),
        }
        _queue(
            kind,
            kwargs,
            [
                ("Date", str(entry_date)),
                ("Asset", chosen),
                ("Quantity sold", f"{quantity:g} {unit}"),
                ("Proceeds", money(proceeds)),
                ("Fees", money(fees)),
                ("Net received", money(net)),
                ("Cost basis", money(cost_basis)),
                ("Realized gain", money(realized, signed=True)),
                ("Received in", _summary_account(account_id)),
            ],
            candidates,
        )


# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------
def _reconcile_form(user: str) -> None:
    kind = "reconcile"
    prefix = f"rec_{_ver(kind)}"
    rows = list_accounts(user, active_only=True)
    if not rows:
        empty_state("Add an account first.")
        return
    labels = {account_label(row): str(row.get("AccountID")) for row in rows}
    c1, c2 = st.columns([1, 1.4])
    entry_date = c1.date_input("Date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    with c2:
        chosen = st.selectbox("Account", options=list(labels), key=f"{prefix}_account")
    account_id = labels.get(chosen, "")
    account = get_account(account_id)
    balances = compute_balances(user, active_only=False)
    raw_balance = balances.get(account_id, 0)
    liability = str(account.get("Kind", "")).strip().lower() in {"credit_card", "loan"}
    display = outstanding(account, raw_balance) if account else 0
    label = "Actual outstanding (₹)" if liability else "Actual balance (₹)"
    c3, c4 = st.columns([1, 1])
    actual = _amount_input(label, f"{prefix}_actual", default_paise=display, min_value=-1_000_000_000.0)
    reason = c3.selectbox(
        "Reason",
        ["Bank charge", "Interest", "Missed entry", "Correction", "Other"],
        key=f"{prefix}_reason",
    )
    note = c4.text_input("Note", key=f"{prefix}_note")
    st.caption(f"App balance: {money(display)} · difference will be posted as one adjustment.")
    confirmed = st.checkbox("I understand this writes a permanent adjustment", key=f"{prefix}_confirmed")

    if st.button("Review entry", type="primary", key=f"{prefix}_review"):
        actual_signed = -actual if liability else actual
        diff = actual_signed - raw_balance
        if diff == 0:
            st.error("Actual balance already matches. Nothing to reconcile.")
            return
        if not confirmed:
            st.error("Tick the confirmation checkbox first.")
            return
        kwargs = {
            "user": user,
            "entry_date": entry_date,
            "account_id": account_id,
            "actual_balance_paise": actual_signed,
            "reason": reason,
            "note": note or "",
            "client_request_id": _req(kind),
        }
        _queue(
            kind,
            kwargs,
            [
                ("Date", str(entry_date)),
                ("Account", chosen),
                ("App balance", money(display)),
                ("Actual", money(actual)),
                ("Adjustment", money(diff, signed=True)),
                ("Reason", reason),
                ("Note", note or "—"),
            ],
        )


# ---------------------------------------------------------------------------
# setup entries
# ---------------------------------------------------------------------------
def render_new_account_form(user: str) -> None:
    kind = "account"
    prefix = f"acct_{_ver(kind)}"
    c1, c2 = st.columns([1.2, 1])
    nickname = c1.text_input("Nickname", key=f"{prefix}_nickname", placeholder="Salary account")
    kind_value = c2.selectbox(
        "Kind",
        options=["savings", "current", "wallet", "cash", "brokerage", "loan"],
        format_func=lambda value: value.replace("_", " ").title(),
        key=f"{prefix}_kind",
    )
    c3, c4 = st.columns([1, 1])
    institution = c3.text_input("Institution / provider", key=f"{prefix}_institution", placeholder="Bank, wallet, broker")
    currency = c4.text_input("Currency", value="INR", key=f"{prefix}_currency")
    c5, c6 = st.columns([1, 1])
    opening_label = "Opening outstanding (₹)" if kind_value == "loan" else "Opening balance (₹)"
    opening = _amount_input(opening_label, f"{prefix}_opening")
    opening_date = c6.date_input("Opening date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    notes = st.text_input("Notes", key=f"{prefix}_notes")

    if st.button("Review account", type="primary", key=f"{prefix}_review"):
        try:
            nickname_clean = str(nickname or "").strip()
            if not nickname_clean:
                raise ValueError("Nickname is required.")
            duplicate = find_nickname_duplicate(user, nickname_clean)
            candidates = []
            if duplicate:
                candidates.append(
                    {
                        "kind": "account",
                        "row": {
                            "Date": str(duplicate.get("Timestamp", ""))[:10],
                            "Description": f"Existing account: {duplicate.get('Nickname', '')}",
                            "Amount": duplicate.get("OpeningBalance", 0),
                            "AccountID": duplicate.get("AccountID", ""),
                        },
                        "reason": "same nickname",
                    }
                )
            kwargs = {
                "user": user,
                "nickname": nickname_clean,
                "kind": kind_value,
                "institution": institution or "",
                "currency": currency or "INR",
                "opening_balance_paise": opening,
                "opening_date": opening_date,
                "notes": notes or "",
            }
            _queue(
                kind,
                kwargs,
                [
                    ("Nickname", nickname_clean),
                    ("Kind", kind_value.replace("_", " ").title()),
                    ("Institution", institution or "—"),
                    ("Currency", currency or "INR"),
                    (opening_label.replace(" (₹)", ""), money(opening)),
                    ("Opening date", str(opening_date)),
                    ("Notes", notes or "—"),
                ],
                candidates,
            )
        except Exception as exc:
            st.error(str(exc))


def render_new_card_form(user: str) -> None:
    kind = "card"
    prefix = f"card_{_ver(kind)}"
    c1, c2 = st.columns([1.2, 1])
    nickname = c1.text_input("Card nickname", key=f"{prefix}_nickname", placeholder="HDFC Regalia")
    issuer = c2.text_input("Issuer / bank", key=f"{prefix}_issuer", placeholder="HDFC")
    c3, c4, c5 = st.columns([1, 1, 1])
    limit = _amount_input("Credit limit (₹)", f"{prefix}_limit")
    opening = _amount_input("Opening outstanding (₹)", f"{prefix}_opening")
    opening_date = c5.date_input("Opening date", value=date.today(), max_value=date.today(), key=f"{prefix}_date")
    c6, c7, c8 = st.columns([1, 1, 1])
    statement_day = c6.number_input("Statement day (optional)", min_value=0, max_value=31, value=0, step=1, key=f"{prefix}_statement")
    due_day = c7.number_input("Due day", min_value=1, max_value=31, value=10, step=1, key=f"{prefix}_due")
    currency = c8.text_input("Currency", value="INR", key=f"{prefix}_currency")
    notes = st.text_input("Notes", key=f"{prefix}_notes")

    if st.button("Review card", type="primary", key=f"{prefix}_review"):
        try:
            nickname_clean = str(nickname or "").strip()
            if not nickname_clean:
                raise ValueError("Card nickname is required.")
            if limit <= 0:
                raise ValueError("Credit limit must be greater than zero.")
            duplicate = find_nickname_duplicate(user, nickname_clean)
            candidates = []
            if duplicate:
                candidates.append(
                    {
                        "kind": "card",
                        "row": {
                            "Date": str(duplicate.get("Timestamp", ""))[:10],
                            "Description": f"Existing account: {duplicate.get('Nickname', '')}",
                            "Amount": duplicate.get("CreditLimit", 0),
                            "AccountID": duplicate.get("AccountID", ""),
                        },
                        "reason": "same nickname",
                    }
                )
            kwargs = {
                "user": user,
                "nickname": nickname_clean,
                "kind": "credit_card",
                "institution": issuer or "",
                "currency": currency or "INR",
                "opening_balance_paise": opening,
                "opening_date": opening_date,
                "credit_limit_paise": limit,
                "statement_day": int(statement_day) or "",
                "due_day": int(due_day),
                "notes": notes or "",
            }
            _queue(
                kind,
                kwargs,
                [
                    ("Nickname", nickname_clean),
                    ("Issuer", issuer or "—"),
                    ("Credit limit", money(limit)),
                    ("Opening outstanding", money(opening)),
                    ("Available limit", money(max(0, limit - opening))),
                    ("Statement day", str(int(statement_day)) if statement_day else "Optional / skipped"),
                    ("Due day", str(int(due_day))),
                    ("Opening date", str(opening_date)),
                ],
                candidates,
            )
        except Exception as exc:
            st.error(str(exc))


def render_limit_form(user: str) -> None:
    kind = "limit"
    prefix = f"lim_{_ver(kind)}"
    c1, c2 = st.columns([1, 1.3])
    scope = c1.selectbox("Scope", options=SCOPES, format_func=lambda value: value.title(), key=f"{prefix}_scope")
    target_id = ""
    if scope == "category":
        target_id = _category_select("Category", "Expenditure", f"{prefix}_target", "")
    elif scope == "account":
        rows = list_accounts(user, active_only=True)
        labels = {account_label(row): str(row.get("AccountID")) for row in rows}
        if labels:
            chosen = c2.selectbox("Account", options=list(labels), key=f"{prefix}_account")
            target_id = labels.get(chosen, "")
    c3, c4, c5 = st.columns([1, 1, 1])
    period_choice = c3.selectbox(
        "Period",
        options=["Monthly recurring", "Specific month"],
        key=f"{prefix}_period",
    )
    if period_choice == "Specific month":
        month = c4.date_input("Month", value=date.today(), key=f"{prefix}_month")
        period = f"month:{month.strftime('%Y-%m')}"
    else:
        period = "monthly"
    amount = _amount_input("Limit amount (₹)", f"{prefix}_amount")
    warn = c5.number_input("Warn at %", min_value=1, max_value=100, value=80, step=5, key=f"{prefix}_warn")
    active = st.checkbox("Active", value=True, key=f"{prefix}_active")

    if st.button("Review limit", type="primary", key=f"{prefix}_review"):
        if amount <= 0:
            st.error("Limit must be greater than zero.")
            return
        if scope != "overall" and not target_id:
            st.error("Choose a category or account.")
            return
        kwargs = {
            "user": user,
            "scope": scope,
            "period": period,
            "amount_paise": amount,
            "target_id": target_id,
            "warn_at_pct": int(warn),
            "is_active": active,
        }
        target_label = "—"
        if scope == "category":
            target_label = next((r["Category"] for r in list_categories("Expenditure") if r["CategoryID"] == target_id), "—")
        elif scope == "account":
            target_label = _summary_account(target_id)
        _queue(
            kind,
            kwargs,
            [
                ("Scope", scope.title()),
                ("Target", target_label),
                ("Period", period_choice),
                ("Amount", money(amount)),
                ("Warn at", f"{int(warn)}%"),
                ("Active", "Yes" if active else "No"),
            ],
        )


def render_bill_form(user: str) -> None:
    kind = "bill"
    prefix = f"bill_{_ver(kind)}"
    rows = list_accounts(user, active_only=True)
    c1, c2 = st.columns([1.2, 1])
    name = c1.text_input("Bill name", key=f"{prefix}_name", placeholder="Internet, rent, insurance")
    amount = c2.number_input("Amount (₹)", min_value=0.0, step=100.0, format="%.2f", key=f"{prefix}_amount")
    c3, c4 = st.columns([1, 1])
    labels = {account_label(row): str(row.get("AccountID")) for row in rows}
    if labels:
        chosen = c3.selectbox("Account / card", options=list(labels), key=f"{prefix}_account")
        account_id = labels.get(chosen, "")
    else:
        account_id = ""
    category_id_value = _category_select("Category", "Expenditure", f"{prefix}_cat", "")
    c5, c6, c7 = st.columns([1, 1, 1])
    frequency = c4.selectbox("Frequency", options=FREQUENCIES, key=f"{prefix}_frequency")
    next_due = c5.date_input("Next due date", value=date.today() + timedelta(days=7), key=f"{prefix}_due")
    remind = c6.number_input("Remind days before", min_value=0, max_value=60, value=7, step=1, key=f"{prefix}_remind")
    notify = c7.selectbox("Notify via", options=NOTIFY_CHANNELS, key=f"{prefix}_notify", format_func=lambda value: value.replace("_", " "))
    active = st.checkbox("Active", value=True, key=f"{prefix}_active")

    if st.button("Review bill", type="primary", key=f"{prefix}_review"):
        if not name.strip():
            st.error("Bill name is required.")
            return
        if amount <= 0:
            st.error("Amount must be greater than zero.")
            return
        if not account_id:
            st.error("Choose an account or card.")
            return
        kwargs = {
            "user": user,
            "name": name,
            "amount_paise": to_paise(amount),
            "account_id": account_id,
            "category_id": category_id_value,
            "frequency": frequency,
            "next_due_date": next_due,
            "remind_days_before": int(remind),
            "notify_via": notify,
            "auto_post": False,
            "is_active": active,
        }
        _queue(
            kind,
            kwargs,
            [
                ("Name", name),
                ("Amount", money(to_paise(amount))),
                ("Account", _summary_account(account_id)),
                ("Category", next((r["Category"] for r in list_categories("Expenditure") if r["CategoryID"] == category_id_value), "—")),
                ("Frequency", frequency.title()),
                ("Next due", str(next_due)),
                ("Remind", f"{int(remind)} days before"),
                ("Notify", notify.replace("_", " ")),
                ("Active", "Yes" if active else "No"),
            ],
        )


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------
FORM_RENDERERS = {
    "expense": _expense_form,
    "income": _income_form,
    "transfer": _transfer_form,
    "card_payment": _card_payment_form,
    "stock_buy": _stock_buy_form,
    "stock_sell": _stock_sell_form,
    "asset_buy": _asset_buy_form,
    "asset_sell": _asset_sell_form,
    "reconcile": _reconcile_form,
    "account": render_new_account_form,
    "card": render_new_card_form,
    "limit": render_limit_form,
    "bill": render_bill_form,
}


def render() -> None:
    user = st.session_state.get("current_user")
    if not user:
        st.error("Select a profile in the sidebar.")
        return
    page_header(
        "New entry",
        "One compact form. Review, then save. The ledger is append-only.",
        "capture",
    )
    upcoming = upcoming_rules(user, within_days=7)
    due_strip(upcoming)

    labels = [label for label, _ in ENTRY_OPTIONS]
    if "entry_type_pill" not in st.session_state:
        st.session_state["entry_type_pill"] = "Expense"
    selected_label = st.pills(
        "Entry type",
        options=labels,
        selection_mode="single",
        key="entry_type_pill",
        label_visibility="collapsed",
        wrap=True,
    )
    kind = LABEL_TO_KIND.get(selected_label or "Expense", "expense")
    st.markdown("<div style='height:0.35rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        FORM_RENDERERS[kind](user)
