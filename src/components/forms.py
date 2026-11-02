import datetime
import streamlit as st
from src.config import ACCOUNT_TYPES
from src.database import append_row, get_registered_accounts, get_active_categories, add_category

def render_transaction_form(active_user):
    st.subheader("📝 Log Financial Entry")
    
    entry_type = st.radio("Select Entry Type", ["Expenditure", "Income", "Investment"], horizontal=True)
    dynamic_accounts = get_registered_accounts(active_user)
    date = st.date_input("Transaction Date", datetime.date.today())
    
    if entry_type == "Income":
        st.markdown("---")
        st.markdown("### 💵 Income Entry Details")
        
        income_source = st.selectbox(
            "Select Income Source Category",
            [
                "Savings Bank Interest",
                "Fixed Deposit (FD) Interest",
                "Salary & Wages",
                "Brokerage - Dividend",
                "Brokerage - Capital Gain / Asset Sale",
                "Rental & Property Income",
                "Freelance & Secondary Income",
                "Gifts, Refunds & Other"
            ]
        )
        
        amount = 0.0
        account = dynamic_accounts[0] if dynamic_accounts else "Default Bank"
        category = income_source
        desc_parts = []
        
        # 1. Savings Bank Interest
        if income_source == "Savings Bank Interest":
            col1, col2 = st.columns(2)
            with col1:
                bank_name = st.text_input("Bank Name", placeholder="e.g. HDFC Bank, ICICI Bank")
            with col2:
                amount = st.number_input("Interest Amount Received", min_value=0.0, format="%.2f")
            account = bank_name if bank_name else "Savings Bank"
            desc_parts.append(f"Savings Interest credited from {bank_name if bank_name else 'Bank'}")

        # 2. Fixed Deposit Interest
        elif income_source == "Fixed Deposit (FD) Interest":
            col1, col2, col3 = st.columns(3)
            with col1:
                bank_name = st.text_input("Bank / Financial Institution", placeholder="e.g. SBI, Post Office")
            with col2:
                amount = st.number_input("Net Interest Received", min_value=0.0, format="%.2f")
            with col3:
                tds_amount = st.number_input("TDS Deducted (if any)", min_value=0.0, format="%.2f")
            fd_ref = st.text_input("FD Receipt / Reference No. (Optional)")
            account = bank_name if bank_name else "FD Account"
            desc_parts.append(f"FD Interest ({bank_name}) - Ref: {fd_ref} | TDS: ₹{tds_amount:.2f}")

        # 3. Salary & Wages
        elif income_source == "Salary & Wages":
            col1, col2, col3 = st.columns(3)
            with col1:
                company_name = st.text_input("Employer Name", placeholder="e.g. Tech Corp")
            with col2:
                pay_type = st.selectbox("Pay Component", ["Monthly Net Salary", "Bonus / Variable Pay", "Reimbursement", "Severance"])
            with col3:
                amount = st.number_input("Net Amount Credited", min_value=0.0, format="%.2f")
            account = st.selectbox("Credited To Account", dynamic_accounts)
            desc_parts.append(f"{pay_type} from {company_name}")

        # 4. Brokerage - Dividend
        elif income_source == "Brokerage - Dividend":
            col1, col2 = st.columns(2)
            with col1:
                ticker_name = st.text_input("Stock / Mutual Fund / ETF Ticker", placeholder="e.g. Reliance, NIFTY 50 ETF")
            with col2:
                amount = st.number_input("Dividend Amount Received", min_value=0.0, format="%.2f")
            account = st.selectbox("Credited Demat / Bank Account", dynamic_accounts)
            desc_parts.append(f"Dividend from {ticker_name}")

        # 5. Brokerage - Capital Gain / Asset Sale
        elif income_source == "Brokerage - Capital Gain / Asset Sale":
            col1, col2, col3 = st.columns(3)
            with col1:
                asset_name = st.text_input("Asset / Stock Name", placeholder="e.g. Infosys Shares, Gold ETF")
            with col2:
                sale_value = st.number_input("Total Sale Value Received", min_value=0.0, format="%.2f")
            with col3:
                cost_basis = st.number_input("Original Purchase Cost (Cost Basis)", min_value=0.0, format="%.2f")
            amount = sale_value
            net_gain = sale_value - cost_basis
            account = st.selectbox("Credited To Account", dynamic_accounts)
            desc_parts.append(f"Sale of {asset_name} | Net Realized Gain/Loss: ₹{net_gain:,.2f}")

        # 6. Rental & Property Income
        elif income_source == "Rental & Property Income":
            col1, col2 = st.columns(2)
            with col1:
                property_ident = st.text_input("Property / Tenant Name", placeholder="e.g. Apartment 302, John Doe")
            with col2:
                amount = st.number_input("Rent Amount Received", min_value=0.0, format="%.2f")
            account = st.selectbox("Credited To Account", dynamic_accounts)
            desc_parts.append(f"Rent collected for {property_ident}")

        # 7. Freelance & Secondary Income
        elif income_source == "Freelance & Secondary Income":
            col1, col2 = st.columns(2)
            with col1:
                client_name = st.text_input("Client / Project Name", placeholder="e.g. Website Redesign")
            with col2:
                amount = st.number_input("Payment Amount", min_value=0.0, format="%.2f")
            account = st.selectbox("Credited To Account", dynamic_accounts)
            desc_parts.append(f"Freelance payment from {client_name}")

        # 8. Gifts, Refunds & Other
        elif income_source == "Gifts, Refunds & Other":
            col1, col2 = st.columns(2)
            with col1:
                other_source = st.text_input("Source Description", placeholder="e.g. Income Tax Refund, Gift from Parents")
            with col2:
                amount = st.number_input("Amount Received", min_value=0.0, format="%.2f")
            account = st.selectbox("Credited To Account", dynamic_accounts)
            desc_parts.append(f"Received from {other_source}")

        private_flag = st.checkbox("Keep Private (Hide from combined view)")
        
        if st.button("🚀 Log Income Entry", type="primary"):
            if amount <= 0:
                st.error("Please enter a valid amount greater than zero.")
            else:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                final_description = " | ".join(desc_parts)
                row_data = [
                    timestamp,
                    str(date),
                    active_user,
                    "Income",
                    account,
                    amount,
                    category,
                    final_description,
                    str(private_flag)
                ]
                try:
                    append_row("Transactions", row_data)
                    st.success(f"Logged ₹{amount:,.2f} under {category} successfully!")
                except Exception as e:
                    st.error(f"Failed to log transaction: {e}")

    else:
        # Standard form handling for Expenditure & Investment entries
        with st.form("standard_form", clear_on_submit=True):
            account = st.selectbox("Account / Source", dynamic_accounts)
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            
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
        with st.form("category_form", clear_on_submit=True):
            cat_type = st.radio("Category Assignment", ["Expenditure", "Income", "Investment"], horizontal=True)
            cat_name = st.text_input("New Category Name (e.g., Freelance Project, Subscriptions)")
            
            cat_submitted = st.form_submit_button("Save Category")
            if cat_submitted:
                if cat_name.strip():
                    add_category(cat_type, cat_name.strip())
                    st.success(f"New {cat_type} category '{cat_name}' added successfully!")
                else:
                    st.error("Please enter a valid category name.")