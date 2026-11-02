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

def get_or_create_worksheet(wb, target_title):
    """Safely finds a worksheet case-insensitively, or creates it with correct schema headers."""
    headers = SHEET_SCHEMAS.get(target_title, [])
    for ws in wb.worksheets():
        if ws.title.strip().lower() == target_title.strip().lower():
            existing_values = ws.get_all_values()
            if not existing_values and headers:
                ws.append_row(headers)
            return ws
            
    ws = wb.add_worksheet(title=target_title, rows=100, cols=max(len(headers), 5))
    if headers:
        ws.append_row(headers)
    return ws

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

def add_category(category_type: str, category_name: str):
    wb = get_connection()
    sheet = get_or_create_worksheet(wb, "Categories")
    sheet.append_row([category_type, category_name])

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