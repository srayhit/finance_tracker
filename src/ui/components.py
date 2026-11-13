"""Small HTML helpers for the compact UI."""

from __future__ import annotations

import html
from datetime import date

import streamlit as st

from src.services.accounts import account_label
from src.utils.money import format_inr

TYPE_LABELS = {
    "expense": "Expense",
    "income": "Income",
    "transfer": "Transfer",
    "stock_buy": "Stock buy",
    "stock_sell": "Stock sell",
    "asset_purchase": "Asset buy",
    "asset_sale": "Asset sell",
    "adjustment": "Reconcile",
    "reversal": "Reversal",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def page_header(title: str, subtitle: str = "", kicker: str = "") -> None:
    kicker_html = f'<div class="fin-kicker">{esc(kicker)}</div>' if kicker else ""
    subtitle_html = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f'<div class="fin-header"><div>{kicker_html}<h1>{esc(title)}</h1>{subtitle_html}</div></div>',
        unsafe_allow_html=True,
    )


def stat(label: str, value: str, hint: str = "", tone: str = "") -> str:
    cls = {"good": "fin-good", "warn": "fin-warn", "bad": "fin-bad", "accent": "fin-accent"}.get(tone, "")
    hint_html = f'<div class="h">{esc(hint)}</div>' if hint else ""
    return (
        f'<div class="fin-stat"><div class="k">{esc(label)}</div>'
        f'<div class="v {cls}">{esc(value)}</div>{hint_html}</div>'
    )


def stats_grid(items: list[dict]) -> None:
    cards = "".join(stat(**item) for item in items)
    st.markdown(f'<div class="fin-stats">{cards}</div>', unsafe_allow_html=True)


def summary(rows: list[tuple[str, str]]) -> None:
    body = "".join(
        f'<div class="fin-summary-row"><div class="k">{esc(key)}</div>'
        f'<div class="v">{esc(value)}</div></div>'
        for key, value in rows
    )
    st.markdown(f'<div class="fin-summary">{body}</div>', unsafe_allow_html=True)


def empty_state(text: str) -> None:
    st.markdown(f'<div class="fin-empty">{esc(text)}</div>', unsafe_allow_html=True)


def money(paise: object, signed: bool = False) -> str:
    return format_inr(paise, signed=signed)


def account_name(account: dict | None) -> str:
    return account_label(account) if account else "—"


def chips(values: list[str]) -> None:
    if not values:
        return
    body = "".join(f'<span class="fin-chip">{esc(value)}</span>' for value in values)
    st.markdown(body, unsafe_allow_html=True)


def due_strip(upcoming: list[dict]) -> None:
    if not upcoming:
        return
    items = []
    for rule in upcoming[:4]:
        days = int(rule.get("DaysUntilDue", 0))
        when = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days}d")
        items.append(f"<span><b>{esc(rule.get('Name', 'Bill'))}</b> · {esc(when)}</span>")
    st.markdown(
        '<div class="fin-due"><span class="fin-accent">Upcoming</span>'
        + "".join(items)
        + "</div>",
        unsafe_allow_html=True,
    )


def type_label(value: str) -> str:
    return TYPE_LABELS.get(str(value).strip().lower(), str(value).title())


def candidate_html(candidate: dict, account_lookup: dict[str, dict] | None = None) -> str:
    row = candidate.get("row", {})
    account_lookup = account_lookup or {}
    account = account_lookup.get(str(row.get("AccountID", "")))
    amount = format_inr(row.get("Amount") or row.get("NetAmount"))
    when = str(row.get("Date", ""))[:10]
    description = str(row.get("Description", "") or row.get("Notes", "")) or "No description"
    return (
        f'<div class="fin-candidate">'
        f'<div><b>{esc(when)}</b> · <span class="mono">{esc(amount)}</span> · '
        f'{esc(account_label(account) if account else "")}</div>'
        f'<div class="fin-muted">{esc(description)}</div>'
        f'<div class="fin-muted" style="font-size:0.72rem">{esc(candidate.get("reason", ""))}</div>'
        f"</div>"
    )
