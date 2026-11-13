"""Preferences, payment defaults, categories and data/privacy status."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db.repo import (
    clear_cache,
    get_meta,
    read_any_tab,
    read_tab,
    refresh_worksheet_index,
)
from src.db.schemas import (
    ACCOUNT_KINDS,
    METHOD_LABELS,
    PAYMENT_METHODS,
)
from src.services.accounts import account_label, list_accounts
from src.services.categories import (
    CATEGORY_TYPES,
    ensure_category,
    list_categories,
    set_category_active,
)
from src.services.settings import (
    get_settings,
    list_payment_defaults,
    save_payment_defaults,
    save_settings,
)
from src.ui.components import empty_state, esc, money, page_header, summary
from src.utils.ids import as_int
from src.utils.money import from_paise, to_paise

ALERT_OPTIONS = [("in_app", "In app"), ("email", "Email"), ("both", "Both")]


def _preferences(user: str) -> None:
    settings = get_settings(user)
    with st.form("preferences_form"):
        c1, c2, c3 = st.columns(3)
        currency = c1.text_input("Currency", value=str(settings.get("Currency", "INR")))
        month_start = c2.number_input(
            "Month starts on day",
            min_value=1,
            max_value=28,
            value=int(as_int(settings.get("MonthStartDay"), 1)),
            step=1,
        )
        utilization = c3.number_input(
            "Card utilization warning %",
            min_value=1,
            max_value=100,
            value=int(as_int(settings.get("CardUtilWarnPct"), 30)),
            step=5,
        )
        c4, c5 = st.columns(2)
        low_floor = c4.number_input(
            "Low balance floor (₹)",
            min_value=0.0,
            value=from_paise(settings.get("LowLimitFloor")),
            step=100.0,
            format="%.2f",
        )
        default_budget = c5.number_input(
            "Default monthly budget (₹)",
            min_value=0.0,
            value=from_paise(settings.get("DefaultBudget")),
            step=100.0,
            format="%.2f",
        )
        c6, c7 = st.columns([1, 1.6])
        alert_values = [value for value, _ in ALERT_OPTIONS]
        alert_labels = dict(ALERT_OPTIONS)
        current_alert = str(settings.get("AlertPrefs", "in_app"))
        alert = c6.selectbox(
            "Alerts",
            options=alert_values,
            index=alert_values.index(current_alert) if current_alert in alert_values else 0,
            format_func=lambda value: alert_labels.get(value, value),
        )
        email = c7.text_input(
            "Notification email", value=str(settings.get("NotificationEmail", ""))
        )
        st.markdown("**Duplicate protection**")
        d1, d2, d3, d4 = st.columns(4)
        window = d1.number_input(
            "Window (days)",
            min_value=1,
            max_value=365,
            value=int(as_int(settings.get("DuplicateWindowDays"), 45)),
            step=1,
        )
        date_days = d2.number_input(
            "Date tolerance (days)",
            min_value=0,
            max_value=30,
            value=int(as_int(settings.get("DuplicateDateDays"), 2)),
            step=1,
        )
        amount_pct = d3.number_input(
            "Amount tolerance %",
            min_value=0.0,
            max_value=50.0,
            value=float(settings.get("DuplicateAmountPct") or 2),
            step=0.5,
            format="%.1f",
        )
        description_pct = d4.number_input(
            "Description similarity %",
            min_value=50,
            max_value=100,
            value=int(as_int(settings.get("DuplicateDescriptionPct"), 85)),
            step=5,
        )
        privacy = st.text_input(
            "Privacy toggles",
            value=str(settings.get("PrivacyToggles", "")),
            placeholder="Comma-separated flags, optional",
            help="Free-form flags for future privacy controls. No card numbers in any field.",
        )
        submitted = st.form_submit_button("Save preferences", type="primary")
    if submitted:
        try:
            save_settings(
                user,
                {
                    "Currency": (currency or "INR").strip().upper(),
                    "MonthStartDay": int(month_start),
                    "CardUtilWarnPct": int(utilization),
                    "LowLimitFloor": to_paise(low_floor),
                    "DefaultBudget": to_paise(default_budget),
                    "AlertPrefs": alert,
                    "NotificationEmail": email.strip(),
                    "DuplicateWindowDays": int(window),
                    "DuplicateDateDays": int(date_days),
                    "DuplicateAmountPct": amount_pct,
                    "DuplicateDescriptionPct": int(description_pct),
                    "PrivacyToggles": privacy.strip(),
                },
            )
            st.toast("Preferences saved.", icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _payment_defaults(user: str) -> None:
    accounts = list_accounts(user, active_only=True)
    st.caption(
        "Defaults only prefill the source account. Every entry still shows a final confirmation."
    )
    if not accounts:
        empty_state("Add an account or card first.")
        return
    choices = {"— none —": ""}
    choices.update({account_label(row): str(row.get("AccountID")) for row in accounts})
    current = {
        str(row.get("Method", "")).strip().lower(): str(row.get("DefaultAccountID", "")).strip()
        for row in list_payment_defaults(user)
    }
    positions = {value: index for index, value in enumerate(choices.values())}
    methods = [*PAYMENT_METHODS, "bill_payment"]
    with st.form("payment_defaults_form"):
        columns = st.columns(2)
        selected: dict[str, str] = {}
        for index, method in enumerate(methods):
            column = columns[index % 2]
            current_id = current.get(method, "")
            label = METHOD_LABELS.get(method, method.replace("_", " ").title())
            selected[method] = column.selectbox(
                label,
                options=list(choices),
                index=positions.get(current_id, 0),
                key=f"default_{method}",
            )
        submitted = st.form_submit_button("Save defaults", type="primary")
    if submitted:
        try:
            save_payment_defaults(
                user,
                {method: choices.get(label, "") for method, label in selected.items()},
            )
            st.toast("Payment defaults saved.", icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _categories() -> None:
    st.caption("Categories are shared reference data for this spreadsheet.")
    category_type = st.radio(
        "Type",
        options=CATEGORY_TYPES,
        horizontal=True,
        key="settings_category_type",
        label_visibility="collapsed",
    )
    rows = list_categories(category_type, active_only=False)
    if not rows:
        empty_state("No categories of this type.")
    columns = st.columns(2)
    for index, row in enumerate(rows):
        category_id = str(row.get("CategoryID"))
        active = str(row.get("IsActive", "TRUE")).strip().lower() not in {
            "false",
            "0",
            "no",
        }
        value = columns[index % 2].checkbox(
            str(row.get("Category", "")),
            value=active,
            key=f"category_active_{category_id}",
        )
        if value != active:
            set_category_active(category_id, value)
            st.rerun()
    st.markdown("---")
    with st.form("new_category_form"):
        c1, c2 = st.columns([2, 1])
        name = c1.text_input("New category", placeholder="Pets, insurance, ...")
        chosen_type = c2.selectbox(
            "Type",
            options=CATEGORY_TYPES,
            index=CATEGORY_TYPES.index(category_type),
        )
        submitted = st.form_submit_button("Add category")
    if submitted:
        try:
            ensure_category(name, chosen_type)
            st.toast("Category added.", icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _audit_table(user: str) -> pd.DataFrame:
    frame = read_tab("Audit")
    if frame.empty:
        return pd.DataFrame()
    rows = [
        row for row in frame.to_dict("records") if str(row.get("User", "")).strip() == user
    ]
    rows.sort(key=lambda row: str(row.get("Timestamp", "")), reverse=True)
    display = [
        {
            "When": str(row.get("Timestamp", ""))[:19].replace("T", " "),
            "Action": row.get("Action", ""),
            "Tab": row.get("Tab", ""),
            "Record": str(row.get("RecordID", ""))[:40],
            "Batch": row.get("WriteBatchID", ""),
        }
        for row in rows[:25]
    ]
    return pd.DataFrame(display)


def _data_privacy(user: str) -> None:
    summary(
        [
            ("Schema", get_meta("SchemaVersion") or "—"),
            ("App", get_meta("AppVersion") or "—"),
            ("Bootstrapped", (get_meta("BootstrappedAt") or "—")[:19].replace("T", " ")),
            ("Lexicon", get_meta("LexiconVersion") or "—"),
            ("Legacy backups", get_meta("LegacyBackups") or "—"),
            ("Owner", get_meta("Owner") or get_meta("Users") or "—"),
        ]
    )
    st.caption(
        "Only nicknames and opaque IDs are stored. Account numbers are rejected in nicknames, "
        "and card-like digit strings in free text are redacted before saving."
    )
    c1, c2 = st.columns([1, 3])
    if c1.button("Refresh cached reads", key="refresh_sheets"):
        refresh_worksheet_index()
        clear_cache()
        st.toast("Cache cleared. Reloading from the sheet.", icon="✅")
        st.rerun()
    c2.caption(
        "Use this after editing the Google Sheet directly. No credential values are ever shown."
    )

    st.markdown("### Audit trail")
    audit = _audit_table(user)
    if audit.empty:
        empty_state("No audit rows for this spreadsheet yet.")
    else:
        st.dataframe(audit, hide_index=True, width="stretch")

    with st.expander("Legacy backups (read-only)"):
        st.caption(
            "Bootstrap copied the old tabs to _v1_* before writing v2 reference data. "
            "The old Transactions and Investments tabs are also preserved untouched."
        )
        for tab in ("_v1_Accounts", "_v1_CreditCards", "_v1_Categories"):
            try:
                frame = read_any_tab(tab)
            except Exception as exc:
                st.warning(f"Could not read {tab}: {exc}")
                continue
            if frame.empty:
                st.caption(f"{tab}: empty or missing")
                continue
            st.markdown(f"**{tab}** · {len(frame):,} rows")
            st.dataframe(frame, hide_index=True, width="stretch")


def render() -> None:
    user = st.session_state.get("current_user")
    if not user:
        st.error("Select a spreadsheet in the sidebar.")
        return

    page_header(
        "Settings",
        "Preferences, account defaults, categories and the local audit trail.",
        "control",
    )
    tab_prefs, tab_defaults, tab_categories, tab_data = st.tabs(
        ["Preferences", "Payment defaults", "Categories", "Data & privacy"]
    )
    with tab_prefs:
        _preferences(user)
    with tab_defaults:
        _payment_defaults(user)
    with tab_categories:
        _categories()
    with tab_data:
        _data_privacy(user)
