"""Recurring bill reminders and spending limits. No auto-posting in v1."""

from __future__ import annotations

from datetime import date

import streamlit as st

from src.services.accounts import account_map
from src.services.categories import category_map
from src.services.limits import list_limits, save_limit, set_limit_active, spent_for_limit
from src.services.recurring import (
    list_rules,
    mark_paid,
    set_rule_active,
    upcoming_rules,
)
from src.ui.components import (
    account_name,
    empty_state,
    esc,
    money,
    page_header,
    stats_grid,
)
from src.ui.pages.entry import render_bill_form, render_limit_form
from src.utils.ids import as_int


def _active(value: object) -> bool:
    return str(value if value is not None else "TRUE").strip().lower() not in {
        "false",
        "0",
        "no",
        "off",
    }


def _due_text(days: int | None) -> tuple[str, str]:
    if days is None:
        return "—", ""
    if days < 0:
        return f"overdue by {abs(days)}d", "bad"
    if days == 0:
        return "today", "warn"
    if days == 1:
        return "tomorrow", "warn"
    if days <= 7:
        return f"in {days}d", "warn"
    return f"in {days}d", ""


def _bill_block(rule: dict, user: str, due_days: int | None) -> None:
    rule_id = str(rule.get("RuleID"))
    active = _active(rule.get("IsActive"))
    due_text, tone = _due_text(due_days)
    accounts = account_map(user, active_only=False)
    categories = category_map()
    account = accounts.get(str(rule.get("AccountID", "")).strip())
    category = categories.get(str(rule.get("CategoryID", "")).strip(), {})
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2.3, 1.15, 1.3, 0.75])
        c1.markdown(
            f"**{esc(rule.get('Name', 'Bill'))}**  \n"
            f"<span class='fin-muted'>{esc(str(rule.get('Frequency', 'monthly')).title())} · "
            f"{esc(account_name(account))} · {esc(category.get('Category', 'No category'))}</span>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            f"<div class='mono' style='font-size:1.02rem'>{money(rule.get('Amount'))}</div>"
            f"<div class='fin-muted' style='font-size:0.72rem'>amount</div>",
            unsafe_allow_html=True,
        )
        next_due = str(rule.get("NextDueDate", ""))[:10] or "—"
        c3.markdown(
            f"<div class='mono' style='font-size:1.02rem'>{esc(next_due)}</div>"
            f"<div class='fin-muted {('fin-' + tone) if tone else ''}' style='font-size:0.72rem'>"
            f"{esc(due_text)}</div>",
            unsafe_allow_html=True,
        )
        with c4:
            value = st.toggle("Active", value=active, key=f"bill_active_{rule_id}")
            if value != active:
                set_rule_active(rule_id, value)
                st.rerun()
        b1, b2 = st.columns([1, 3])
        if b1.button("Mark paid", key=f"bill_paid_{rule_id}"):
            try:
                mark_paid(rule_id)
                st.toast("Moved to the next cycle.", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        b2.caption(
            f"Remind {int(as_int(rule.get('RemindDaysBefore'), 7))} days before · "
            f"{str(rule.get('NotifyVia', 'in_app')).replace('_', ' ')}"
        )


def _limit_block(limit: dict, user: str) -> None:
    limit_id = str(limit.get("LimitID"))
    spent = spent_for_limit(limit, user)
    amount = as_int(limit.get("Amount"))
    pct = (spent / amount * 100.0) if amount else 0.0
    active = _active(limit.get("IsActive"))
    categories = category_map()
    accounts = account_map(user, active_only=False)
    scope = str(limit.get("Scope", "")).strip().lower()
    if scope == "category":
        target = categories.get(str(limit.get("TargetID", "")).strip(), {}).get(
            "Category", "Category"
        )
    elif scope == "account":
        target = account_name(accounts.get(str(limit.get("TargetID", "")).strip()))
    else:
        target = "All spending"
    period = str(limit.get("Period", "monthly"))
    period_label = (
        "this month"
        if period == "monthly"
        else period.split(":", 1)[-1] if period.startswith("month:") else period
    )
    tone = "bad" if pct >= 100 else "warn" if pct >= float(limit.get("WarnAtPct") or 80) else "good"
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2.3, 1.15, 1.15, 0.75])
        c1.markdown(
            f"**{esc(scope.title())} · {esc(target)}**  \n"
            f"<span class='fin-muted'>{esc(period_label)} · warn at "
            f"{int(as_int(limit.get('WarnAtPct'), 80))}%</span>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            f"<div class='mono' style='font-size:1.02rem'>{money(spent)}</div>"
            f"<div class='fin-muted' style='font-size:0.72rem'>spent</div>",
            unsafe_allow_html=True,
        )
        c3.markdown(
            f"<div class='mono' style='font-size:1.02rem'>{money(amount)}</div>"
            f"<div class='fin-muted' style='font-size:0.72rem'>limit</div>",
            unsafe_allow_html=True,
        )
        with c4:
            value = st.toggle("Active", value=active, key=f"limit_active_{limit_id}")
            if value != active:
                set_limit_active(limit_id, value)
                st.rerun()
        st.progress(min(1.0, max(0.0, pct / 100.0)), text=f"{pct:.0f}% used")
        if pct >= 100:
            st.caption(f"Over limit by {money(spent - amount)}.")
        elif pct >= float(limit.get("WarnAtPct") or 80):
            st.caption(f"Close to limit · {money(max(0, amount - spent))} left.")


def render() -> None:
    user = st.session_state.get("current_user")
    if not user:
        st.error("Select a profile in the sidebar.")
        return

    page_header(
        "Bills & limits",
        "Reminders only. Nothing is posted automatically; you confirm every ledger entry.",
        "planning",
    )
    rules = list_rules(user, active_only=False)
    limits = list_limits(user, active_only=False)
    due_map = {
        str(rule.get("RuleID")): rule.get("DaysUntilDue")
        for rule in upcoming_rules(user, within_days=366)
    }
    soon = [
        rule
        for rule in upcoming_rules(user, within_days=7)
        if int(rule.get("DaysUntilDue", 0)) >= 0
    ]
    over = 0
    for limit in limits:
        if not _active(limit.get("IsActive")):
            continue
        amount = as_int(limit.get("Amount"))
        if amount and spent_for_limit(limit, user) >= amount:
            over += 1
    stats_grid(
        [
            {"label": "Active bills", "value": f"{len([r for r in rules if _active(r.get('IsActive'))]):,}"},
            {
                "label": "Due in 7 days",
                "value": money(sum(as_int(rule.get("Amount")) for rule in soon)),
                "hint": f"{len(soon)} reminder(s)",
                "tone": "warn" if soon else "",
            },
            {
                "label": "Active limits",
                "value": f"{len([l for l in limits if _active(l.get('IsActive'))]):,}",
            },
            {"label": "Over limit", "value": f"{over:,}", "tone": "bad" if over else ""},
        ]
    )

    tab_bills, tab_limits, tab_new_bill, tab_new_limit = st.tabs(
        ["Bills", "Limits", "Add bill", "Add limit"]
    )
    with tab_bills:
        if not rules:
            empty_state("No recurring bills yet. Add one from the Add bill tab.")
        for rule in rules:
            _bill_block(rule, user, due_map.get(str(rule.get("RuleID"))))
    with tab_limits:
        if not limits:
            empty_state("No spending limits yet. Add one from the Add limit tab.")
        for limit in limits:
            _limit_block(limit, user)
    with tab_new_bill:
        render_bill_form(user)
    with tab_new_limit:
        render_limit_form(user)
