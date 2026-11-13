"""Spreadsheet data sources configured in ``.streamlit/secrets.toml``.

Example::

    [spreadsheets]
    Home = "1AbC..."
    Business = "9XyZ..."

Only aliases reach the UI. Spreadsheet IDs stay in secrets and are read here on
demand; nothing in this module renders them.
"""

from __future__ import annotations

import streamlit as st

STATE_KEY = "active_source"
LEGACY_ALIAS = "Default sheet"


def _configured() -> dict[str, str]:
    """Alias -> spreadsheet ID, in TOML order. Never expose the IDs outside this module."""
    try:
        table = st.secrets.get("spreadsheets")
    except Exception as exc:
        raise RuntimeError(
            "Could not read .streamlit/secrets.toml. Add a [spreadsheets] table."
        ) from exc

    sources: dict[str, str] = {}
    if table and not hasattr(table, "items"):
        raise ValueError(
            "[spreadsheets] must be a TOML table of alias = \"spreadsheet id\" entries."
        )
    if table:
        for raw_alias, raw_id in table.items():
            alias = str(raw_alias).strip()
            if not alias:
                continue
            if not isinstance(raw_id, str):
                raise ValueError(
                    f"Spreadsheet alias {alias!r} must map to a spreadsheet ID string."
                )
            sheet_id = raw_id.strip()
            if not sheet_id or any(character.isspace() for character in sheet_id):
                raise ValueError(f"Spreadsheet alias {alias!r} has an invalid ID.")
            if alias in sources:
                raise ValueError("Spreadsheet aliases must be unique.")
            if sheet_id in sources.values():
                raise ValueError(
                    "Each spreadsheet ID may only be configured under one alias."
                )
            sources[alias] = sheet_id
    if sources:
        return sources

    # One-time compatibility with the previous single-sheet secrets layout.
    legacy = st.secrets.get("spreadsheet")
    legacy_id = str(legacy.get("id", "")).strip() if hasattr(legacy, "get") else ""
    if legacy_id and not any(character.isspace() for character in legacy_id):
        return {LEGACY_ALIAS: legacy_id}

    raise RuntimeError(
        "No spreadsheets are configured. Add a [spreadsheets] table to "
        '.streamlit/secrets.toml with alias = "spreadsheet id" entries.'
    )


def list_aliases() -> list[str]:
    return list(_configured())


def source_id(alias: str) -> str:
    sources = _configured()
    if alias not in sources:
        raise ValueError("Unknown spreadsheet alias.")
    return sources[alias]


def ensure_active_source() -> str:
    """Set a valid active alias in session state and return it."""
    aliases = list_aliases()
    active = str(st.session_state.get(STATE_KEY) or "").strip()
    if active not in aliases:
        active = aliases[0]
        st.session_state[STATE_KEY] = active
    st.session_state["current_user"] = active
    return active


def active_alias() -> str:
    return ensure_active_source()


def active_spreadsheet_id() -> str:
    return source_id(active_alias())


def set_active_source(alias: str) -> None:
    """Confirm a new data source. Any unconfirmed write plan belongs to the old sheet."""
    if alias not in list_aliases():
        raise ValueError("Unknown spreadsheet alias.")
    st.session_state[STATE_KEY] = alias
    st.session_state["current_user"] = alias
    st.session_state.pop("pending_plan", None)
