import datetime
import streamlit as st
from src.config import ACCOUNT_TYPES, DEFAULT_CATEGORIES
from src.database import get_connection

def render_transaction_form(active_user):
    st.subheader("📝 Log New Financial Entry")
    
    with st.form("transaction_form", clear_on_submit=True):
        entry_type = st.radio("Select Entry Type", ["Expenditure", "Income", "Investment"], horizontal=True)
        date = st.date_input("Date")
        account = st.selectbox("Account / Asset", ACCOUNT_TYPES)
        amount = st.number_input("Amount", min_value=0.0, format="%.2f")
        
        # Select categories based on entry type
        categories = DEFAULT_CATEGORIES.get(entry_type, ["General"])
        category = st.selectbox("Category", categories)
        
        description = st.text_input("Description / Notes")
        private_flag = st.checkbox("Keep Private (Hide from combined family view)")
        
        submitted = st.form_submit_button("🚀 Submit Entry")
        
        if submitted:
            if amount <= 0:
                st.error("Please enter a valid amount greater than zero.")
            else:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row_data = [
                    timestamp,
                    str(date),
                    active_user,
                    entry_type,
                    account,
                    amount,
                    category,
                    description,
                    str(private_flag)
                ]
                try:
                    sh = get_connection()
                    worksheet = sh.worksheet("Transactions")
                    worksheet.append_row(row_data)
                    st.success("Entry successfully logged to Google Sheets!")
                except Exception as e:
                    st.error(f"Failed to save entry: {e}")