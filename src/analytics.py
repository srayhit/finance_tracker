import pandas as pd

def filter_visible_data(df, active_user, view_mode):
    if df.empty or "User" not in df.columns:
        return df
    if view_mode == "Individual":
        return df[df["User"] == active_user]
    else:
        if "Private" in df.columns:
            return df[(df["Private"].astype(str).str.lower() != "true") | (df["User"] == active_user)]
        return df

def calculate_kpis(df, active_user, view_mode):
    filtered_df = filter_visible_data(df, active_user, view_mode)
    if filtered_df.empty or "Amount" not in filtered_df.columns:
        return 0.0, 0.0, 0.0, 0.0
        
    filtered_df["Amount"] = pd.to_numeric(filtered_df["Amount"], errors="coerce").fillna(0)
    
    total_income = filtered_df[filtered_df["Type"] == "Income"]["Amount"].sum()
    total_expenditure = filtered_df[filtered_df["Type"] == "Expenditure"]["Amount"].sum()
    net_savings = total_income - total_expenditure
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0
    
    return total_income, total_expenditure, net_savings, savings_rate