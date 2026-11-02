# src/config.py

SPREADSHEET_NAME = "Personal_Finance_Tracker"

USERS = ["Admin (Master)", "Sarah", "Mike"]

ACCOUNT_TYPES = ["Savings", "Current", "Salary", "UPI / Wallet", "Credit Card"]

DEFAULT_CATEGORIES = {
    "Expenditure": ["Groceries", "Rent", "Utilities", "Transport", "Entertainment", "Celebration Expenses", "Dining Out"],
    "Income": [
        "Salary", 
        "Savings Bank Interest", 
        "Fixed Deposits Interest", 
        "Dividends from Brokerage", 
        "Gifts from Family", 
        "Asset Sale", 
        "Other"
    ],
    "Investment": ["Mutual Funds", "Direct Equity", "Bonds", "PPF", "Real Estate"]
}

# Strict column schemas for every worksheet
SHEET_SCHEMAS = {
    "Transactions": ["Timestamp", "Date", "User", "Type", "Account", "Amount", "Category", "Description", "Private"],
    "Categories": ["Type", "Category"],
    "Investments": ["Timestamp", "Date", "User", "AssetName", "InvestedAmount", "CurrentValue"],
    "CreditCards": ["Timestamp", "User", "BankName", "CardName", "DueDate", "CreditLimit"],
    "Accounts": ["Timestamp", "User", "BankName", "AccountType", "AccountName"]
}