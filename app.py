import streamlit as st
from src.profile_selector import render_profile_selector
from src.database import load_data
from src.analytics import calculate_kpis, filter_visible_data
from src.components.forms import render_transaction_form
from src.components.charts import plot_expense_donut, plot_monthly_trend_bar, render_balance_table

st.set_page_config(page_title="Personal Finance Tracker", page_icon="💰", layout="wide")

st.title("📊 Cloud-Native Personal Finance Tracker")

active_user, view_mode = render_profile_selector()
page = st.sidebar.radio("Navigation", ["Dashboard", "Log Entry"])

df_transactions = load_data("Transactions")

if page == "Log Entry":
    render_transaction_form(active_user)
elif page == "Dashboard":
    st.subheader(f"Financial Overview ({view_mode} View - {active_user})")
    
    income, expenditure, savings, savings_rate = calculate_kpis(df_transactions, active_user, view_mode)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Income", f"₹{income:,.2f}")
    col2.metric("Total Expenditure", f"₹{expenditure:,.2f}")
    col3.metric("Net Savings", f"₹{savings:,.2f}")
    col4.metric("Savings Rate", f"{savings_rate:.1f}%")
    
    st.markdown("---")
    
    chart_df = filter_visible_data(df_transactions, active_user, view_mode)
    
    col_left, col_right = st.columns(2)
    with col_left:
        plot_expense_donut(chart_df)
    with col_right:
        plot_monthly_trend_bar(chart_df)
        
    render_balance_table(chart_df)