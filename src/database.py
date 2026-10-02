import streamlit as st
import gspread
import pandas as pd
from datetime import datetime

import gspread
import streamlit as st
from src.config import SPREADSHEET_NAME

def get_connection():
    # Connect using service account from Streamlit secrets
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    sh = gc.open(SPREADSHEET_NAME)
    return sh

@st.cache_resource
def get_gspread_client():
    """Initializes and caches the Google Sheets client using Streamlit secrets."""
    credentials = dict(st.secrets["gcp_service_account"])
    # Handle newline escaping for private key
    if "\\n" in credentials["private_key"]:
        credentials["private_key"] = credentials["private_key"].replace("\\n", "\n")
    return gspread.service_account_from_dict(credentials)

def get_workbook():
    client = get_gspread_client()
    return client.open_by_key(st.secrets["spreadsheet"]["id"])

def load_data() -> tuple[pd.DataFrame, list[str], list[str]]:
    """Fetches transactions and dynamic categories from the Google Sheet."""
    wb = get_workbook()
    
    # 1. Load Transactions Sheet
    try:
        tx_sheet = wb.worksheet("Transactions")
    except gspread.exceptions.WorksheetNotFound:
        tx_sheet = wb.add_worksheet(title="Transactions", rows=1, cols=8)
        tx_sheet.append_row(["Date", "User", "Type", "Category", "Amount", "Account", "Description", "Is_Private"])
    
    tx_records = tx_sheet.get_all_records()
    df = pd.DataFrame(tx_records)
    
    if df.empty:
        df = pd.DataFrame(columns=["Date", "User", "Type", "Category", "Amount", "Account", "Description", "Is_Private"])
    else:
        df["Date"] = pd.to_datetime(df["Date"])
        df["Amount"] = pd.to_numeric(df["Amount"])
        df["Is_Private"] = df["Is_Private"].astype(bool)

    # 2. Load Custom Categories Sheet
    try:
        cat_sheet = wb.worksheet("Categories")
        cat_records = cat_sheet.get_all_records()
        cat_df = pd.DataFrame(cat_records)
    except gspread.exceptions.WorksheetNotFound:
        cat_sheet = wb.add_worksheet(title="Categories", rows=1, cols=2)
        cat_sheet.append_row(["Type", "Category"])
        from src.config import DEFAULT_CATEGORIES
        initial_rows = []
        for t, cats in DEFAULT_CATEGORIES.items():
            for c in cats:
                initial_rows.append([t, c])
        if initial_rows:
            cat_sheet.append_rows(initial_rows)
        cat_df = pd.DataFrame(initial_rows, columns=["Type", "Category"])

    income_cats = cat_df[cat_df["Type"] == "Income"]["Category"].tolist()
    expense_cats = cat_df[cat_df["Type"] == "Expense"]["Category"].tolist()
    
    return df, income_cats, expense_cats

def append_row(row_data: list):
    """Appends a new transaction row to the Google Sheet."""
    wb = get_workbook()
    sheet = wb.worksheet("Transactions")
    sheet.append_row(row_data)

def add_category(category_type: str, category_name: str):
    """Adds a custom category to the dynamic Category sheet."""
    wb = get_workbook()
    sheet = wb.worksheet("Categories")
    sheet.append_row([category_type, category_name])
