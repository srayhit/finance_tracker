"""Ledger review, filters and reversals. Read-only history plus audited reversal."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.db.repo import read_any_tab
from src.services.accounts import account_map
from src.services.categories import category_map
from src.services.ledger import (
    get_entry,
    outstanding,
    recent_entries,
    reverse_entry,
    reversed_entry_ids,
)
from src.services.recurring import upcoming_rules
from src.services.tagging import tag_name_map
from src.ui.components import (
    account_name,
    due_strip,
    empty_state,
    money,
    page_header,
    stats_grid,
    summary,
    type_label,
)
from src.ui.pages.entry import queue_plan
from src.utils.ids import as_int
from src.utils.money import to_paise

IGNORED_STATUSES = {"pending", "void", "cancelled", "failed"}
TYPE_FILTERS = [
    "expense",
    "income",
    "transfer",
    "stock_buy",
    "stock_sell",
    "asset_purchase",
    "asset_sale",
    "adjustment",
    "reversal",
]


def _effective(row: dict) -> bool:
    return str(row.get("Status", "")).strip().lower() not in IGNORED_STATUSES


def _posted(row: dict) -> bool:
    return str(row.get("Status", "")).strip().lower() in {"posted", ""}


def _entry_label(row: dict) -> str:
    when = str(row.get("Date", ""))[:10]
    amount = money(row.get("Amount"))
    description = str(row.get("Description", "")).strip() or type_label(row.get("Type", ""))
    return f"{when} · {type_label(row.get('Type', ''))} · {amount} · {description[:52]}"


def _rows_for_display(
    rows: list[dict],
    accounts: dict[str, dict],
    categories: dict[str, dict],
    tags: dict[str, str],
) -> list[dict]:
    display = []
    for row in rows:
        category = categories.get(str(row.get("CategoryID", "")).strip(), {})
        tag_names = [
            tags.get(value, value)
            for value in str(row.get("Tags", "")).split(",")
            if value.strip()
        ]
        display.append(
            {
                "Date": str(row.get("Date", ""))[:10],
                "Type": type_label(row.get("Type", "")),
                "Amount": money(row.get("Amount")),
                "Fees": money(row.get("Fees")) if as_int(row.get("Fees")) else "",
                "Account": account_name(accounts.get(str(row.get("AccountID", "")).strip())),
                "To / card": account_name(
                    accounts.get(str(row.get("CounterAccountID", "")).strip())
                )
                if row.get("CounterAccountID")
                else "",
                "Category": category.get("Category", ""),
                "Description": row.get("Description", ""),
                "Tags": ", ".join(tag_names),
                "Status": str(row.get("Status", "")).title(),
                "Private": "Yes" if str(row.get("IsPrivate", "")).upper() == "TRUE" else "",
            }
        )
    return display


def _month_totals(rows: list[dict]) -> tuple[int, int]:
    month = date.today().strftime("%Y-%m")
    reversed_ids = {
        str(row.get("LinkedEntryID", "")).strip()
        for row in rows
        if str(row.get("Type", "")).strip().lower() == "reversal"
        and str(row.get("LinkedEntryID", "")).strip()
    }
    income = 0
    spend = 0
    for row in rows:
        if not _effective(row) or not str(row.get("Date", "")).startswith(month):
            continue
        if str(row.get("EntryID", "")).strip() in reversed_ids:
            continue
        entry_type = str(row.get("Type", "")).strip().lower()
        if entry_type == "income":
            income += as_int(row.get("Amount"))
        elif entry_type in {"expense", "asset_purchase"}:
            spend += as_int(row.get("Amount"))
    return income, spend


def render() -> None:
    user = st.session_state.get("current_user")
    if not user:
        st.error("Select a profile in the sidebar.")
        return

    page_header(
        "Ledger",
        "Append-only cash history. Balances are derived, never edited by hand.",
        "review",
    )
    due_strip(upcoming_rules(user, within_days=7))

    entries = recent_entries(user, limit=None)
    posted = [row for row in entries if _effective(row)]
    income, spend = _month_totals(posted)
    cards = [
        row
        for row in entries
        if str(row.get("Type", "")).strip().lower() == "transfer"
        and row.get("CounterAccountID")
    ]

    stats_grid(
        [
            {"label": "This month in", "value": money(income), "tone": "good"},
            {"label": "This month out", "value": money(spend), "tone": "warn"},
            {"label": "Net", "value": money(income - spend, signed=True)},
            {"label": "Entries", "value": f"{len(posted):,}", "hint": f"{len(cards):,} transfers"},
        ]
    )

    if not entries:
        empty_state("No ledger entries yet. Add your first entry from the New entry page.")
        return

    with st.expander("Filters", expanded=False):
        f1, f2, f3 = st.columns([1.6, 1.4, 1.4])
        search = f1.text_input("Search description", key="ledger_search")
        selected_types = f2.multiselect(
            "Type",
            options=TYPE_FILTERS,
            format_func=type_label,
            key="ledger_types",
        )
        all_time = f3.checkbox("All time", value=False, key="ledger_all_time")
        d1, d2 = st.columns(2)
        start = d1.date_input(
            "From", value=date.today() - timedelta(days=90), key="ledger_from"
        )
        end = d2.date_input("To", value=date.today(), key="ledger_to")

    filtered = []
    for row in entries:
        if not all_time:
            row_date = str(row.get("Date", ""))[:10]
            if row_date < str(start) or row_date > str(end):
                continue
        if selected_types and str(row.get("Type", "")).strip().lower() not in selected_types:
            continue
        if search and search.strip().lower() not in str(row.get("Description", "")).lower():
            continue
        filtered.append(row)

    accounts = account_map(user, active_only=False)
    categories = category_map()
    tags = tag_name_map(user)
    display = _rows_for_display(filtered, accounts, categories, tags)
    if display:
        st.dataframe(
            pd.DataFrame(display),
            hide_index=True,
            width="stretch",
            height=min(560, 38 + 35 * len(display)),
        )
    else:
        empty_state("No entries match these filters.")

    st.markdown("### Reverse an entry")
    reversed_ids = reversed_entry_ids(user)
    eligible = [
        row
        for row in entries
        if str(row.get("Type", "")).strip().lower() != "reversal"
        and str(row.get("EntryID", "")).strip() not in reversed_ids
        and _posted(row)
    ]
    if not eligible:
        empty_state("Nothing to reverse. Reversed entries are locked.")
        _render_legacy()
        return

    labels = {str(row.get("EntryID")): _entry_label(row) for row in eligible}
    selected_id = st.selectbox(
        "Entry",
        options=list(labels),
        format_func=lambda value: labels.get(value, value),
        key="reverse_entry_id",
    )
    original = get_entry(selected_id, user)
    if original:
        account = accounts.get(str(original.get("AccountID", "")).strip())
        category = categories.get(str(original.get("CategoryID", "")).strip(), {})
        summary(
            [
                ("Date", str(original.get("Date", ""))[:10]),
                ("Type", type_label(original.get("Type", ""))),
                ("Amount", money(original.get("Amount"))),
                ("Account", account_name(account)),
                ("Category", category.get("Category", "—")),
                ("Description", original.get("Description") or "—"),
                ("Status", str(original.get("Status", "")).title()),
            ]
        )
    r1, r2 = st.columns([2, 1])
    reason = r1.text_input(
        "Why reverse this entry?", key="reverse_reason", placeholder="Wrong amount, duplicate, ..."
    )
    reversal_date = r2.date_input(
        "Reversal date", value=date.today(), max_value=date.today(), key="reverse_date"
    )
    st.caption(
        "The original stays in the ledger. A mirrored reversal is posted and both are linked."
    )
    if st.button("Review reversal", type="primary", key="reverse_review"):
        if not reason.strip():
            st.error("A reason is required for a reversal.")
            return
        queue_plan(
            "reversal",
            {
                "user": user,
                "entry_id_value": selected_id,
                "reason": reason.strip(),
                "reversal_date": reversal_date,
            },
            [
                ("Action", "Reverse entry"),
                ("Original", labels.get(selected_id, selected_id)),
                ("Reversal date", str(reversal_date)),
                ("Reason", reason.strip()),
            ],
        )

    _render_legacy()


def _render_legacy() -> None:
    with st.expander("Legacy data (read-only, not imported)"):
        st.caption(
            "The v1 tabs are preserved as-is. They are not merged into the v2 ledger."
        )
        for tab in ("Transactions", "Investments"):
            try:
                frame = read_any_tab(tab)
            except Exception as exc:
                st.warning(f"Could not read {tab}: {exc}")
                continue
            if frame.empty:
                st.caption(f"{tab}: empty")
                continue
            st.markdown(f"**{tab}** · {len(frame):,} rows")
            st.dataframe(frame, hide_index=True, width="stretch")
