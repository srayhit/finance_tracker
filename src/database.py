import gspread
import pandas as pd
import streamlit as st
from src.config import SPREADSHEET_NAME, SHEET_SCHEMAS, DEFAULT_CATEGORIES

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
    """Ensures worksheets exist and have a single header row without inserting duplicates."""
    try:
        wb = get_connection()
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return

    existing_worksheets = {ws.title.strip().lower(): ws for ws in wb.worksheets()}
    
    for tab_name, headers in SHEET_SCHEMAS.items():
        target_lower = tab_name.strip().lower()
        
        if target_lower not in existing_worksheets:
            # 1. Sheet doesn't exist -> Create and append headers as row 1
            ws = wb.add_worksheet(title=tab_name, rows=100, cols=max(len(headers), 5))
            ws.append_row(headers)
        else:
            ws = existing_worksheets[target_lower]
            all_rows = ws.get_all_values()
            
            if not all_rows:
                # 2. Sheet is empty -> Append headers
                ws.append_row(headers)
            else:
                # 3. Sheet has data -> Check if row 1 is already the exact header row
                first_row_normalized = [str(cell).strip().lower() for cell in all_rows[0]]
                headers_normalized = [str(h).strip().lower() for h in headers]
                
                # Only insert headers if Row 1 is NOT the header row and no header row exists in top 5 rows
                if first_row_normalized != headers_normalized:
                    header_already_present = any(
                        [str(c).strip().lower() for c in row] == headers_normalized
                        for row in all_rows[:5]
                    )
                    if not header_already_present:
                        ws.insert_row(headers, index=1)

def get_or_create_worksheet(wb, target_title):
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

def add_category(category_type: str, category_name: str):
    wb = get_connection()
    sheet = get_or_create_worksheet(wb, "Categories")
    sheet.append_row([category_type, category_name])

def get_registered_accounts(active_user):
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

def get_active_categories(entry_type: str):
    df_cats = load_data("Categories")
    
    if not df_cats.empty and "Type" in df_cats.columns and "Category" in df_cats.columns:
        filtered = df_cats[df_cats["Type"].str.lower() == entry_type.lower()]
        if not filtered.empty:
            return filtered["Category"].dropna().astype(str).tolist()
            
    return DEFAULT_CATEGORIES.get(entry_type, ["General"])