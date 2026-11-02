import datetime
import streamlit as st
from src.config import ACCOUNT_TYPES
from src.database import append_row, get_registered_accounts, get_active_categories, add_category

def render_transaction_form(active_user):
    st.subheader("📝 Log New Financial Entry")
    
    dynamic_accounts = get_registered_accounts(active_user)
    
    with st.form("transaction_form", clear_on_submit=True):
        entry_type = st.radio("Select Entry Type", ["Expenditure", "Income", "Investment"], horizontal=True)
        date = st.date_input("Date")
        account = st.selectbox("Account / Source", dynamic_accounts)
        amount = st.number_input("Amount", min_value=0.0, format="%.2f")
        
        # Categories are pulled dynamically; alphabetizing them automatically groups the Income prefixes!
        categories = sorted(get_active_categories(entry_type))
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
    st.subheader("⚙️ Manage Accounts, Cards & Categories")
    
    tab1, tab2, tab3 = st.tabs(["💳 Add Credit Card", "🏦 Add Bank / UPI Account", "🏷️ Add Category"])
    
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
                
    with tab3:
        # We use dynamic inputs (outside of st.form) so the UI can adapt in real-time
        cat_type = st.radio("Category Assignment", ["Expenditure", "Income", "Investment"], horizontal=True, key="cat_radio")
        
        cat_name_final = ""
        
        if cat_type == "Income":
            inc_group = st.selectbox("Income Group", ["Savings Bank", "Brokerage", "Salary", "Secondary Income", "Other Sources"])
            
            if inc_group == "Savings Bank":
                bank_name = st.text_input("Bank Name")
                if bank_name: cat_name_final = f"Savings Bank - {bank_name.strip()}"
                
            elif inc_group == "Brokerage":
                asset_name = st.text_input("Stock or ETF Name (e.g., Reliance, NIFTY)")
                brok_type = st.selectbox("Transaction Type", ["Dividend", "Asset Sale", "Other Interest"])
                if asset_name: cat_name_final = f"Brokerage - {asset_name.strip()} ({brok_type})"
                
            elif inc_group == "Salary":
                comp_name = st.text_input("Company Name")
                if comp_name: cat_name_final = f"Salary - {comp_name.strip()}"
                
            elif inc_group == "Secondary Income":
                sec_type = st.selectbox("Type", ["House Rent", "Freelance", "Other"])
                if sec_type == "Other":
                    other_sec = st.text_input("Specify Secondary Income")
                    if other_sec: cat_name_final = f"Secondary Income - {other_sec.strip()}"
                else:
                    cat_name_final = f"Secondary Income - {sec_type}"
                    
            elif inc_group == "Other Sources":
                oth_type = st.selectbox("Type", ["Gifts", "Asset Sale (House/Car)", "Other"])
                if oth_type == "Other":
                    other_oth = st.text_input("Specify Other Source")
                    if other_oth: cat_name_final = f"Other Sources - {other_oth.strip()}"
                else:
                    cat_name_final = f"Other Sources - {oth_type}"
        else:
            cat_name = st.text_input(f"New {cat_type} Category Name (e.g., Subscriptions)")
            if cat_name: cat_name_final = cat_name.strip()

        # Submit button for the dynamic UI
        if st.button(f"Save {cat_type} Category", type="primary"):
            if cat_name_final:
                try:
                    add_category(cat_type, cat_name_final)
                    st.success(f"Added successfully! It will now appear as: **{cat_name_final}**")
                except Exception as e:
                    st.error(f"Failed to add category: {e}")
            else:
                st.warning("Please fill in the required fields to generate the category name.")