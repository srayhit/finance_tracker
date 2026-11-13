"""Small typed repository over Google Sheets.

The rest of the app talks in tab names + dict rows. No UI module imports
gspread directly.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import gspread
from gspread.utils import rowcol_to_a1

from src import data_sources
from src.db.schemas import V2_SCHEMAS


def _active_spreadsheet_id() -> str:
    return data_sources.active_spreadsheet_id()


@st.cache_resource(show_spinner=False)
def get_workbook(spreadsheet_id: str):
    """One workbook handle per configured spreadsheet, never shared across IDs."""
    credentials = dict(st.secrets["gcp_service_account"])
    if "\\n" in credentials.get("private_key", ""):
        credentials["private_key"] = credentials["private_key"].replace("\\n", "\n")
    client = gspread.service_account_from_dict(credentials)
    return client.open_by_key(spreadsheet_id)


def _workbook():
    return get_workbook(_active_spreadsheet_id())


def _workbook_id() -> str:
    return str(_workbook().id)


@st.cache_resource(show_spinner=False)
def _worksheet_index() -> dict[str, dict[str, object]]:
    return {}


@st.cache_resource(show_spinner=False)
def _ready_tabs(workbook_id: str) -> set[str]:
    return set()


def _worksheet_map() -> dict[str, object]:
    workbook = _workbook()
    index = _worksheet_index()
    key = str(workbook.id)
    mapping = index.get(key)
    if mapping is None:
        mapping = {
            ws.title.strip().lower(): ws for ws in workbook.worksheets()
        }
        index[key] = mapping
    return mapping


def refresh_worksheet_index() -> None:
    workbook_id = _workbook_id()
    _worksheet_index().pop(workbook_id, None)
    _ready_tabs(workbook_id).clear()


def _find_worksheet(name: str):
    return _worksheet_map().get(name.strip().lower())


def get_worksheet(name: str, create: bool = True):
    ws = _find_worksheet(name)
    if ws is not None:
        return ws
    if not create:
        return None
    headers = V2_SCHEMAS.get(name, [])
    ws = _workbook().add_worksheet(
        title=name, rows=200, cols=max(len(headers), 5)
    )
    if headers:
        ws.append_row(headers, value_input_option="USER_ENTERED")
    _worksheet_map()[name.strip().lower()] = ws
    _ready_tabs(_workbook_id()).add(name)
    return ws


def worksheet_exists(name: str) -> bool:
    return _find_worksheet(name) is not None


def read_values(name: str, create: bool = False) -> list[list[str]]:
    ws = get_worksheet(name, create=create)
    if ws is None:
        return []
    return ws.get_all_values()


def ensure_tab(name: str) -> None:
    headers = V2_SCHEMAS.get(name)
    if not headers:
        return
    ready = _ready_tabs(_workbook_id())
    if name in ready:
        return
    ws = get_worksheet(name, create=True)
    values = ws.get_all_values()
    if not values:
        ws.append_row(headers, value_input_option="USER_ENTERED")
        ready.add(name)
        return
    first = [str(cell).strip() for cell in values[0]]
    if first == headers:
        ready.add(name)
        return
    # Only repair a tab that has no real data rows. Never clobber user data.
    has_data = any(
        any(str(cell).strip() for cell in row) and
        [str(cell).strip() for cell in row] != first
        for row in values[1:]
    )
    if not has_data:
        ws.resize(rows=max(ws.row_count, 2), cols=max(len(headers), ws.col_count, 5))
        ws.update(
            values=[headers],
            range_name="A1",
            value_input_option="USER_ENTERED",
        )
        clear_cache()
        ready.add(name)


def ensure_all_tabs() -> None:
    workbook = _workbook()
    existing = _worksheet_map()
    ready = _ready_tabs(str(workbook.id))
    for name, headers in V2_SCHEMAS.items():
        key = name.strip().lower()
        ws = existing.get(key)
        if ws is None:
            ws = workbook.add_worksheet(
                title=name, rows=200, cols=max(len(headers), 5)
            )
            if headers:
                ws.append_row(headers, value_input_option="USER_ENTERED")
            existing[key] = ws
            ready.add(name)


def read_tab_uncached(name: str) -> pd.DataFrame:
    headers = V2_SCHEMAS.get(name, [])
    ws = get_worksheet(name, create=True)
    values = ws.get_all_values()
    if len(values) <= 1:
        return pd.DataFrame(columns=headers or (values[0] if values else []))
    header = [str(c).strip() for c in values[0]]
    rows = []
    for row in values[1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        if [str(cell).strip() for cell in row] == header:
            continue
        padded = list(row) + [""] * (len(header) - len(row))
        rows.append(padded[: len(header)])
    return pd.DataFrame(rows, columns=header)


@st.cache_data(ttl=45, show_spinner=False)
def _read_tab_cached(name: str, spreadsheet_id: str) -> pd.DataFrame:
    return read_tab_uncached(name)


def read_tab(name: str) -> pd.DataFrame:
    """Cached read scoped to the active spreadsheet, so sources never mix."""
    return _read_tab_cached(name, _active_spreadsheet_id())


def read_any_tab(name: str) -> pd.DataFrame:
    """Read a tab that is not part of the v2 schema (legacy/read-only)."""
    ws = _find_worksheet(name)
    if ws is None:
        return pd.DataFrame()
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header = [str(cell).strip() for cell in values[0]]
    rows = []
    for row in values[1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        if [str(cell).strip() for cell in row] == header:
            continue
        padded = list(row) + [""] * (len(header) - len(row))
        rows.append(padded[: len(header)])
    return pd.DataFrame(rows, columns=header)


def clear_cache() -> None:
    try:
        st.cache_data.clear()
    except Exception:
        pass


def write_raw(name: str, values: list[list[str]]) -> None:
    """Write a rectangular block of values, creating the tab if needed."""
    if not values:
        return
    width = max(len(row) for row in values)
    ws = _find_worksheet(name)
    if ws is None:
        ws = _workbook().add_worksheet(
            title=name, rows=max(len(values), 2), cols=max(width, 5)
        )
        _worksheet_map()[name.strip().lower()] = ws
        _ready_tabs(_workbook_id()).add(name)
    else:
        ws.resize(rows=max(len(values), 2), cols=max(width, ws.col_count, 5))
    padded = [list(row) + [""] * (width - len(row)) for row in values]
    ws.update(values=padded, range_name="A1", value_input_option="USER_ENTERED")
    clear_cache()


def append_rows(name: str, rows: list[dict]) -> None:
    if not rows:
        return
    ensure_tab(name)
    headers = V2_SCHEMAS.get(name) or list(rows[0].keys())
    values = [[row.get(column, "") for column in headers] for row in rows]
    ws = get_worksheet(name)
    ws.append_rows(values, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
    clear_cache()


def write_tab(name: str, rows: list[dict], headers: list[str] | None = None) -> None:
    headers = headers or V2_SCHEMAS.get(name) or list(rows[0].keys() if rows else [])
    if not headers:
        return
    ws = get_worksheet(name, create=True)
    ws.resize(rows=max(len(rows) + 1, 2), cols=max(len(headers), 5))
    values = [headers] + [
        [row.get(column, "") for column in headers] for row in rows
    ]
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")
    clear_cache()


def update_row(name: str, key_column: str, key_value: str, record: dict) -> bool:
    ensure_tab(name)
    ws = get_worksheet(name)
    values = ws.get_all_values()
    if not values:
        return False
    headers = [str(c).strip() for c in values[0]]
    if key_column not in headers:
        return False
    key_index = headers.index(key_column)
    values_row = [record.get(column, "") for column in headers]
    for row_number, row in enumerate(values[1:], start=2):
        if len(row) > key_index and str(row[key_index]).strip() == str(key_value).strip():
            end = rowcol_to_a1(row_number, len(headers))
            ws.update(
                values=[values_row],
                range_name=f"A{row_number}:{end}",
                value_input_option="USER_ENTERED",
            )
            clear_cache()
            return True
    return False


def find_one(name: str, column: str, value: str) -> dict | None:
    df = read_tab(name)
    if df.empty or column not in df.columns:
        return None
    match = df[df[column].astype(str).str.strip() == str(value).strip()]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def get_meta(key: str) -> str | None:
    row = find_one("Meta", "Key", key)
    if not row:
        return None
    value = str(row.get("Value", "")).strip()
    return value or None


def set_meta(key: str, value: str) -> None:
    from src.utils.ids import now_iso

    existing = find_one("Meta", "Key", key)
    record = {"Key": key, "Value": value, "UpdatedAt": now_iso()}
    if existing:
        update_row("Meta", "Key", key, record)
    else:
        append_rows("Meta", [record])
