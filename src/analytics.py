import pandas as pd

def filter_visible_data(df: pd.DataFrame, current_user: str) -> pd.DataFrame:
    """Filters out private data belonging to other users."""
    if df.empty:
        return df
    # Show transaction if it's not private, OR if it belongs to the current user
    # Shared entries belong to "Shared / Family" and are visible unless marked private by a specific user profile
    condition = (~df["Is_Private"]) | (df["User"] == current_user)
    return df[condition].copy()

def calculate_kpis(df: pd.DataFrame) -> dict:
    """Calculates Net Balance, Total Income, and Total Expenses."""
    if df.empty:
        return {"net_balance": 0.0, "total_income": 0.0, "total_expense": 0.0}
    
    income = df[df["Type"] == "Income"]["Amount"].sum()
    expense = df[df["Type"] == "Expense"]["Amount"].sum()
    net = income - expense
    
    return {
        "net_balance": float(net),
        "total_income": float(income),
        "total_expense": float(expense)
    }

def get_category_breakdown(df: pd.DataFrame, tx_type: str) -> pd.DataFrame:
    """Aggregates spending/income totals broken down by Category."""
    filtered = df[df["Type"] == tx_type]
    if filtered.empty:
        return pd.DataFrame(columns=["Category", "Amount"])
    return filtered.groupby("Category", as_index=False)["Amount"].sum()

def get_monthly_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates transactional amounts by Month and Type for trend visualization."""
    if df.empty:
        return pd.DataFrame(columns=["Month", "Type", "Amount"])
    
    df_copy = df.copy()
    df_copy["Month"] = df_copy["Date"].dt.to_period("M").astype(str)
    
    trend = df_copy.groupby(["Month", "Type"], as_index=False)["Amount"].sum()
    return trend
