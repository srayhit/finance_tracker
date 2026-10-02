import streamlit as st
from src.profile_selector import render_profile_selector
from src.database import load_data
from src.analytics import filter_visible_data, calculate_kpis, get_category_breakdown, get_monthly_trends
from src.components.forms import render_transaction_form
from src.components.charts import plot_expense_donut, plot_monthly_trend_bar, render_balance_table

# Page Configuration Initialization
st.set_page_config(
    page_title="Family Finance Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Cloud-Native Personal Finance Tracker")

# 1. Trigger Implicit Multi-user Profile context
render_profile_selector()
current_user = st.session_state["current_user"]

# 2. Fetch Datastore Content live from Google Workspace Sheets API
try:
    raw_df, income_cats, expense_cats = load_data()
except Exception as e:
    st.error(f"Failed to securely authenticate or pull data from Google Cloud Store. Verify your configuration secrets. Details: {e}")
    st.stop()

# 3. Apply Multi-tenant Governance and Isolation
visible_df = filter_visible_data(raw_df, current_user)

# 4. Generate Analytic Calculations Engine Metrics
kpis = calculate_kpis(visible_df)

# 5. Core Metric KPI Card Layout Grid Array
kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
with kpi_col1:
    st.metric(label="Net Portfolio Balance", value=f"${kpis['net_balance']:,.2f}")
with kpi_col2:
    st.metric(label="Total Income Sourced", value=f"${kpis['total_income']:,.2f}", delta_color="normal")
with kpi_col3:
    st.metric(label="Total Outflow Expenses", value=f"${kpis['total_expense']:,.2f}", delta_color="inverse")

st.markdown("---")

# 6. Primary Dual Column Workspace Layout Split
left_panel, right_panel = st.columns([1, 1])

with left_panel:
    # Transaction Processing and Appending UI Block
    render_transaction_form(income_cats, expense_cats)

with right_panel:
    st.subheader("📈 Visualization Panels")
    
    # Process Presentation Datasets
    expense_breakdown = get_category_breakdown(visible_df, "Expense")
    monthly_trends = get_monthly_trends(visible_df)
    
    # Dynamic tab layouts for presentation layers
    tab1, tab2 = st.tabs(["Expense Shares", "Historic Growth Trends"])
    with tab1:
        plot_expense_donut(expense_breakdown)
    with tab2:
        plot_monthly_trend_bar(monthly_trends)

st.markdown("---")

# 7. Balance Sheets Dataframe Overview grid row
render_balance_table(visible_df)

# 8. Raw Historical Log Visualizer
with st.expander("📄 View Auditable Historical Audit Log Rows"):
    if not visible_df.empty:
        st.dataframe(
            visible_df.sort_values(by="Date", ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No recent entries recorded.")
