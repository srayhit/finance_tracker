import datetime
import streamlit as st
from src.config import ACCOUNT_TYPES, DEFAULT_CATEGORIES
from src.database import append_row, get_registered_accounts

def render_transaction_form(active_user):
    st.subheader("📝 Log New Financial Entry")
    
    dynamic_accounts = get_registered_accounts(active_user)
    
    with st.form("transaction_form", clear_on_submit=True):
        entry_type = st.radio("Select Entry Type", ["Expenditure", "Income", "Investment"], horizontal=True)
        date = st.date_input("Date")
        account = st.selectbox("Account / Source", dynamic_accounts)
        amount = st.number_input("Amount", min_value=0.0, format="%.2f")
        
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
                    append_row("Transactions", row_data)
                    st.success("Entry successfully logged to Google Sheets!")
                except Exception as e:
                    st.error(f"Failed to save entry: {e}")

def render_setup_forms(active_user):
    st.subheader("⚙️ Manage Accounts & Credit Cards")
    
    tab1, tab2 = st.tabs(["💳 Add Credit Card", "🏦 Add Bank / UPI Account"])
    
    with tab1:
        with st.form("cc_form", clear_on_submit=True):
            bank_name = st.text_input("Bank Name (e.g., HDFC, ICICI)")
            card_name = st.text_input("Credit Card Name (e.g., Regalia Gold)")
            due_date = st.number_input("Billing Due Date (Day of month)", min_value=1, max_value=31, value=10)
            credit_limit = st.number_input("Credit Limit", min_value=0.0, format="%.2f")
            
            cc_submitted = st.form_submit_button("Save Credit Card")
            if cc_submitted:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row_data = [timestamp, active_user, bank_name, card_name, int(due_date), credit_limit]
                append_row("CreditCards", row_data)
                st.success(f"Credit Card '{card_name}' added successfully!")
                
    with tab2:
        with st.form("acc_form", clear_on_submit=True):
            bank_name_acc = st.text_input("Bank or Provider Name (e.g., SBI, GooglePay UPI)")
            account_type = st.selectbox("Account Type", ACCOUNT_TYPES[:-1])
            account_name = st.text_input("Account Identifier / Nickname (e.g., Primary Salary Account)")
            
            acc_submitted = st.form_submit_button("Save Account")
            if acc_submitted:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row_data = [timestamp, active_user, bank_name_acc, account_type, account_name]
                append_row("Accounts", row_data)
                st.success(f"Account '{account_name}' added successfully!")