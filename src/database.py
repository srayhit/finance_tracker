import gspread
import pandas as pd
import streamlit as st
from src.config import SPREADSHEET_NAME

@st.cache_resource
def get_gspread_client():
    credentials = dict(st.secrets["gcp_service_account"])
    if "\\n" in credentials["private_key"]:
        credentials["private_key"] = credentials["private_key"].replace("\\n", "\n")
    return gspread.service_account_from_dict(credentials)

def get_connection():
    client = get_gspread_client()
    return client.open_by_key(st.secrets["spreadsheet"]["id"])

def get_workbook():
    return get_connection()

def load_data(tab_name="Transactions"):
    try:
        wb = get_connection()
        sheet = wb.worksheet(tab_name)
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        return df
    except Exception:
        return pd.DataFrame()

def append_row(row_data: list):
    wb = get_connection()
    sheet = wb.worksheet("Transactions")
    sheet.append_row(row_data)

def add_category(category_type: str, category_name: str):
    wb = get_connection()
    try:
        sheet = wb.worksheet("Categories")
    except Exception:
        sheet = wb.add_worksheet(title="Categories", rows=1, cols=2)
        sheet.append_row(["Type", "Category"])
    sheet.append_row([category_type, category_name])