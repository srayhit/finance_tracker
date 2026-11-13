"""Sidebar spreadsheet selector.

Only aliases are shown. The spreadsheet ID stays in ``.streamlit/secrets.toml``.
Picking a different alias does nothing until **Confirm switch** is pressed, so a
stray click never changes the sheet mid-form.
"""

from __future__ import annotations

import streamlit as st

from src.data_sources import (
    active_alias,
    list_aliases,
    set_active_source,
    source_id,
)
from src.db.bootstrap import bootstrap
from src.db.repo import clear_cache

WIDGET_KEY = "source_pick_widget"
ERROR_KEY = "source_switch_error"
RESET_KEY = "source_pick_reset"


def _switch(alias: str) -> bool:
    previous = active_alias()
    if alias == previous:
        return True
    pending = st.session_state.get("pending_plan")
    set_active_source(alias)
    try:
        with st.spinner(f"Opening {alias}..."):
            bootstrap(source_id(alias), alias)
    except Exception as exc:
        set_active_source(previous)
        if pending is not None:
            st.session_state["pending_plan"] = pending
        clear_cache()
        st.session_state[ERROR_KEY] = type(exc).__name__
        return False
    clear_cache()
    st.session_state.pop(ERROR_KEY, None)
    st.toast(f"Switched to {alias}.", icon="✅")
    return True


def render_source_selector() -> str:
    """Render the alias dropdown and return the active alias."""
    aliases = list_aliases()
    active = active_alias()

    st.sidebar.title("📚 Data source")

    if st.session_state.pop(RESET_KEY, False):
        st.session_state.pop(WIDGET_KEY, None)

    if st.session_state.get(ERROR_KEY):
        st.sidebar.warning(
            "Could not open that spreadsheet. Staying on the current sheet."
        )
        st.sidebar.caption(f"Switch error: {st.session_state[ERROR_KEY]}")

    if st.session_state.get(WIDGET_KEY) not in aliases:
        st.session_state[WIDGET_KEY] = active

    pick = st.sidebar.selectbox(
        "Spreadsheet",
        options=aliases,
        index=aliases.index(active),
        key=WIDGET_KEY,
    )

    if pick == active:
        st.sidebar.caption(f"Reading only **{active}**.")
        return active

    st.sidebar.caption(f"Reading **{active}** until you confirm the switch.")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Confirm switch", type="primary", key="confirm_source_switch"):
        _switch(pick)
        st.rerun()
    if c2.button("Keep current", key="keep_source"):
        st.session_state[RESET_KEY] = True
        st.rerun()
    return active
