import gspread
import pandas as pd
import streamlit as st
from src.config import SPREADSHEET_NAME, SHEET_SCHEMAS

@st.cache_resource
def get_gspread_client():
    credentials = dict(st.secrets["gcp_service_account"])
    if "\\n" in credentials["private_key"]:
        credentials["private_key"] = credentials["private_key"].replace("\\n", "\n")
    return gspread.service_account_from_dict(credentials)

def get_connection():
    client = get_gspread_client()
    return client.open_by_key(st.secrets["spreadsheet"]["id"])

def initialize_database():
    """Runs on app startup to verify sheets exist and force-insert headers if missing."""
    wb = get_connection()
    existing_worksheets = {ws.title.strip().lower(): ws for ws in wb.worksheets()}
    
    for tab_name, headers in SHEET_SCHEMAS.items():
        target_lower = tab_name.strip().lower()
        
        if target_lower not in existing_worksheets:
            # 1. Sheet doesn't exist at all -> Create it and add headers
            ws = wb.add_worksheet(title=tab_name, rows=100, cols=max(len(headers), 5))
            ws.append_row(headers)
        else:
            # 2. Sheet exists -> Check if headers are present
            ws = existing_worksheets[target_lower]
            try:
                first_row = ws.row_values(1)
            except Exception:
                first_row = []
                
            # If the row is empty, or the first column header doesn't match our schema
            if not first_row or str(first_row[0]).strip().lower() != str(headers[0]).strip().lower():
                # Safely insert the schema headers at Row 1, pushing any existing data down
                ws.insert_row(headers, index=1)

def get_or_create_worksheet(wb, target_title):
    """Fetches the worksheet safely (initialization is already handled globally)."""
    for ws in wb.worksheets():
        if ws.title.strip().lower() == target_title.strip().lower():
            return ws
    return wb.add_worksheet(title=target_title, rows=100, cols=10)

def load_data(tab_name="Transactions"):
    try:
        wb = get_connection()
        sheet = get_or_create_worksheet(wb, tab_name)
        records = sheet.get_all_records()
        return pd.DataFrame(records)
    except Exception:
        return pd.DataFrame()

def append_row(tab_name: str, row_data: list):
    wb = get_connection()
    sheet = get_or_create_worksheet(wb, tab_name)
    sheet.append_row(row_data)

def get_registered_accounts(active_user):
    """Fetches user-specific accounts and credit cards for dynamic dropdowns."""
    df_acc = load_data("Accounts")
    df_cc = load_data("CreditCards")
    
    accounts_list = []
    if not df_acc.empty and "AccountName" in df_acc.columns:
        accounts_list.extend(df_acc["AccountName"].dropna().astype(str).tolist())
        
    if not df_cc.empty and "CardName" in df_cc.columns:
        accounts_list.extend([f"CC: {card}" for card in df_cc["CardName"].dropna().astype(str).tolist()])
        
    if not accounts_list:
        accounts_list = ["Default Savings", "Default UPI"]
        
    return accounts_list