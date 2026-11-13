"""Accounts and cards: balances, limits and safe field edits."""

from __future__ import annotations

import streamlit as st

from src.db.schemas import ACCOUNT_KINDS, CASH_ACCOUNT_KINDS, KIND_LABELS
from src.services.accounts import (
    account_label,
    cards,
    create_account,
    get_account,
    list_accounts,
    set_account_active,
    update_account_fields,
)
from src.services.ledger import available_limit, compute_balances, outstanding
from src.ui.components import empty_state, esc, money, page_header, stats_grid
from src.ui.pages.entry import render_new_account_form, render_new_card_form
from src.utils.ids import as_int
from src.utils.money import from_paise, to_paise


def _cash_rows(user: str) -> list[dict]:
    return list_accounts(user, active_only=True, kinds=CASH_ACCOUNT_KINDS)


def _totals(user: str) -> dict:
    balances = compute_balances(user, active_only=False)
    cash = sum(
        balances.get(str(row.get("AccountID")), 0)
        for row in list_accounts(user, active_only=True, kinds=CASH_ACCOUNT_KINDS)
    )
    card_rows = cards(user)
    card_out = sum(
        outstanding(row, balances.get(str(row.get("AccountID")), 0))
        for row in card_rows
    )
    available = sum(
        available_limit(row, balances.get(str(row.get("AccountID")), 0))
        for row in card_rows
    )
    loans = list_accounts(user, active_only=True, kinds=["loan"])
    loan_out = sum(
        outstanding(row, balances.get(str(row.get("AccountID")), 0)) for row in loans
    )
    return {
        "balances": balances,
        "cash": cash,
        "card_out": card_out,
        "available": available,
        "loan_out": loan_out,
        "cards": card_rows,
    }


def _active_toggle(account: dict, key_prefix: str) -> None:
    account_id = str(account.get("AccountID"))
    active = str(account.get("IsActive", "TRUE")).strip().lower() not in {
        "false",
        "0",
        "no",
        "off",
    }
    value = st.toggle(
        "Active",
        value=active,
        key=f"{key_prefix}_active_{account_id}",
    )
    if value != active:
        set_account_active(account_id, value)
        st.rerun()


def _edit_account(account: dict) -> None:
    account_id = str(account.get("AccountID"))
    with st.expander("Edit details"):
        c1, c2 = st.columns([1.2, 1])
        nickname = c1.text_input(
            "Nickname", value=str(account.get("Nickname", "")), key=f"edit_nick_{account_id}"
        )
        institution = c2.text_input(
            "Institution",
            value=str(account.get("Institution", "")),
            key=f"edit_inst_{account_id}",
        )
        notes = st.text_input(
            "Notes", value=str(account.get("Notes", "")), key=f"edit_notes_{account_id}"
        )
        if st.button("Save details", key=f"edit_save_{account_id}"):
            try:
                update_account_fields(
                    account_id,
                    Nickname=nickname,
                    Institution=institution,
                    Notes=notes,
                )
                st.toast("Account updated.", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _edit_card(account: dict) -> None:
    account_id = str(account.get("AccountID"))
    with st.expander("Edit card"):
        c1, c2 = st.columns([1.2, 1])
        nickname = c1.text_input(
            "Card nickname",
            value=str(account.get("Nickname", "")),
            key=f"edit_card_nick_{account_id}",
        )
        institution = c2.text_input(
            "Issuer",
            value=str(account.get("Institution", "")),
            key=f"edit_card_inst_{account_id}",
        )
        c3, c4, c5 = st.columns([1, 1, 1])
        limit = c3.number_input(
            "Credit limit (₹)",
            min_value=0.0,
            value=from_paise(account.get("CreditLimit")),
            step=1000.0,
            format="%.2f",
            key=f"edit_card_limit_{account_id}",
        )
        statement = c4.number_input(
            "Statement day (0 = skip)",
            min_value=0,
            max_value=31,
            value=int(as_int(account.get("StatementDay"))),
            step=1,
            key=f"edit_card_stmt_{account_id}",
        )
        due = c5.number_input(
            "Due day",
            min_value=0,
            max_value=31,
            value=int(as_int(account.get("DueDay"))),
            step=1,
            key=f"edit_card_due_{account_id}",
        )
        notes = st.text_input(
            "Notes",
            value=str(account.get("Notes", "")),
            key=f"edit_card_notes_{account_id}",
        )
        if st.button("Save card", key=f"edit_card_save_{account_id}"):
            try:
                update_account_fields(
                    account_id,
                    Nickname=nickname,
                    Institution=institution,
                    CreditLimit=to_paise(limit),
                    StatementDay=str(int(statement)) if statement else "",
                    DueDay=str(int(due)) if due else "",
                    Notes=notes,
                )
                st.toast("Card updated.", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _account_block(account: dict, balance_paise: int, key_prefix: str) -> None:
    account_id = str(account.get("AccountID"))
    kind = str(account.get("Kind", "")).strip().lower()
    with st.container(border=True):
        c1, c2, c3 = st.columns([2.4, 1.2, 0.7])
        c1.markdown(
            f"**{esc(account.get('Nickname', 'Unnamed'))}**  \n"
            f"<span class='fin-muted'>{esc(KIND_LABELS.get(kind, kind))}"
            + (
                f" · {esc(account.get('Institution'))}"
                if str(account.get('Institution', '')).strip()
                else ""
            )
            + "</span>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            f"<div class='mono' style='font-size:1.02rem'>{money(balance_paise)}</div>"
            f"<div class='fin-muted' style='font-size:0.72rem'>current balance</div>",
            unsafe_allow_html=True,
        )
        with c3:
            _active_toggle(account, key_prefix)
        _edit_account(account)


def _card_block(account: dict, balance_paise: int, key_prefix: str) -> None:
    account_id = str(account.get("AccountID"))
    out = outstanding(account, balance_paise)
    limit = as_int(account.get("CreditLimit"))
    avail = available_limit(account, balance_paise)
    pct = (out / limit * 100.0) if limit else 0.0
    tone = "fin-bad" if pct >= 80 else "fin-warn" if pct >= 50 else "fin-good"
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2.2, 1.15, 1.15, 0.7])
        c1.markdown(
            f"**{esc(account.get('Nickname', 'Unnamed'))}**  \n"
            f"<span class='fin-muted'>{esc(account.get('Institution') or 'Credit card')}"
            + (
                f" · due day {esc(account.get('DueDay'))}"
                if str(account.get('DueDay', '')).strip()
                else ""
            )
            + "</span>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            f"<div class='mono {tone}' style='font-size:1.02rem'>{money(out)}</div>"
            f"<div class='fin-muted' style='font-size:0.72rem'>outstanding</div>",
            unsafe_allow_html=True,
        )
        c3.markdown(
            f"<div class='mono' style='font-size:1.02rem'>{money(avail)}</div>"
            f"<div class='fin-muted' style='font-size:0.72rem'>available of {money(limit)}</div>",
            unsafe_allow_html=True,
        )
        with c4:
            _active_toggle(account, key_prefix)
        if limit:
            st.progress(min(1.0, max(0.0, pct / 100.0)), text=f"{pct:.0f}% utilized")
        _edit_card(account)


def render() -> None:
    user = st.session_state.get("current_user")
    if not user:
        st.error("Select a profile in the sidebar.")
        return

    page_header(
        "Accounts & cards",
        "Nicknames only. No account or card numbers are stored anywhere.",
        "registry",
    )
    totals = _totals(user)
    stats_grid(
        [
            {"label": "Cash & bank", "value": money(totals["cash"]), "tone": "good"},
            {"label": "Card outstanding", "value": money(totals["card_out"]), "tone": "warn"},
            {"label": "Available limit", "value": money(totals["available"])},
            {"label": "Loan outstanding", "value": money(totals["loan_out"])},
        ]
    )

    tab_accounts, tab_cards, tab_new_account, tab_new_card = st.tabs(
        ["Bank & cash", "Credit cards", "Add account", "Add card"]
    )

    with tab_accounts:
        rows = list_accounts(user, active_only=True, kinds=[*CASH_ACCOUNT_KINDS, "loan"])
        if not rows:
            empty_state("No accounts yet. Add one from the Add account tab.")
        for account in rows:
            _account_block(
                account,
                totals["balances"].get(str(account.get("AccountID")), 0),
                "acct",
            )

    with tab_cards:
        if not totals["cards"]:
            empty_state("No credit cards yet. Add one from the Add card tab.")
        for account in totals["cards"]:
            _card_block(
                account,
                totals["balances"].get(str(account.get("AccountID")), 0),
                "card",
            )

    with tab_new_account:
        render_new_account_form(user)

    with tab_new_card:
        render_new_card_form(user)
