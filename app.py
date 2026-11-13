"""Finance tracker entry point.

The v2 app is append-only: forms queue a plan, the global confirm screen is the
only place that writes, and every write is audited. Dashboards are deliberately
deferred until data entry is tested and confirmed.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Ledger",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.data_sources import active_spreadsheet_id, ensure_active_source  # noqa: E402
from src.db.bootstrap import bootstrap  # noqa: E402
from src.source_selector import render_source_selector  # noqa: E402
from src.ui.pages import accounts, assets, bills, entry, ledger  # noqa: E402
from src.ui.pages import settings as settings_page  # noqa: E402
from src.ui.pages.entry import render_pending_confirmation  # noqa: E402
from src.ui.theme import apply_theme  # noqa: E402

apply_theme()

try:
    st.logo("assets/logo.svg", size="large")
except Exception:
    pass


def _new_entry() -> None:
    entry.render()


def _ledger() -> None:
    ledger.render()


def _holdings() -> None:
    assets.render()


def _accounts() -> None:
    accounts.render()


def _bills() -> None:
    bills.render()


def _settings() -> None:
    settings_page.render()


pages = {
    "Capture": [
        st.Page(_new_entry, title="New entry", url_path="new-entry", default=True),
    ],
    "Review": [
        st.Page(_ledger, title="Ledger", url_path="ledger"),
        st.Page(_holdings, title="Holdings", url_path="holdings"),
    ],
    "Setup": [
        st.Page(_accounts, title="Accounts & cards", url_path="accounts"),
        st.Page(_bills, title="Bills & limits", url_path="bills"),
        st.Page(_settings, title="Settings", url_path="settings"),
    ],
}

try:
    active_alias = ensure_active_source()
    spreadsheet_id = active_spreadsheet_id()
except Exception as exc:
    st.error(
        "No spreadsheets are configured. Add a [spreadsheets] table to "
        ".streamlit/secrets.toml with alias = spreadsheet-id entries."
    )
    st.caption(f"Configuration error: {type(exc).__name__}")
    st.stop()

try:
    with st.spinner("Checking the data store..."):
        bootstrap(spreadsheet_id, active_alias)
except Exception as exc:
    # Still show the selector so a broken sheet can be switched away from.
    try:
        render_source_selector()
    except Exception:
        pass
    st.error(
        "The Google Sheets data store could not be initialised. "
        "Check .streamlit/secrets.toml and the sheet permissions."
    )
    st.caption(f"Startup error: {type(exc).__name__}")
    st.stop()

navigation = st.navigation(pages, position="sidebar")
active_alias = render_source_selector()

if st.session_state.get("pending_plan"):
    render_pending_confirmation(active_alias)
    st.stop()

navigation.run()
