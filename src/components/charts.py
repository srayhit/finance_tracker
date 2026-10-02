import pandas as pd
import plotly.express as px
import streamlit as st

def plot_expense_donut(df):
    if df.empty or "Type" not in df.columns:
        st.info("No transaction data available for expense breakdown.")
        return
    
    exp_df = df[df["Type"] == "Expenditure"]
    if exp_df.empty:
        st.info("No expenditures logged yet.")
        return
        
    exp_df["Amount"] = pd.to_numeric(exp_df["Amount"], errors="coerce")
    
    fig = px.pie(
        exp_df, 
        names="Category", 
        values="Amount", 
        hole=0.4, 
        title="Expenditure Breakdown by Category"
    )
    fig.update_layout(margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

def plot_monthly_trend_bar(df):
    if df.empty or "Date" not in df.columns or "Type" not in df.columns:
        st.info("No data available for monthly trend.")
        return
        
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    
    grouped = df.groupby(["Month", "Type"])["Amount"].sum().reset_index()
    if grouped.empty:
        st.info("Not enough data for cash flow trends.")
        return
        
    fig = px.bar(
        grouped, 
        x="Month", 
        y="Amount", 
        color="Type", 
        barmode="group", 
        title="Monthly Cash Flow Trend"
    )
    fig.update_layout(margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

def render_balance_table(df):
    if df.empty:
        st.info("No accounts or balances recorded yet.")
        return
        
    st.subheader("📋 Account Flow Summary")
    df = df.copy()
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    
    summary = df.groupby(["Account", "Type"])["Amount"].sum().reset_index()
    st.dataframe(summary, use_container_width=True)