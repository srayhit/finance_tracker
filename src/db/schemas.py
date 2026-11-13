"""v2 Google Sheet schemas and reference defaults."""

V2_SCHEMAS = {
    "Meta": ["Key", "Value", "UpdatedAt"],
    "Accounts": [
        "AccountID", "Timestamp", "User", "Nickname", "Kind", "Institution",
        "Currency", "OpeningBalance", "OpeningDate", "CreditLimit",
        "StatementDay", "DueDay", "IsActive", "Notes",
    ],
    "Categories": [
        "CategoryID", "Type", "Category", "ParentCategory", "IsActive",
    ],
    "Tags": [
        "TagID", "Name", "Type", "Aliases", "ParentTag",
        "DefaultCategoryID", "IsActive",
    ],
    "TagRules": [
        "RuleID", "User", "Pattern", "MatchType", "OutputTagIDs", "Channel",
        "CategoryID", "Priority", "Source", "Hits", "LastUsed", "IsActive",
    ],
    "Ledger": [
        "EntryID", "ClientRequestID", "IdempotencyKey", "WriteBatchID",
        "Timestamp", "Date", "User", "Type", "AccountID", "CounterAccountID",
        "Amount", "Fees", "TaxWithheld", "CategoryID", "Description", "Tags",
        "IsPrivate", "Status", "LinkedEntryID", "LinkedTradeID",
        "DuplicateOfEntryID", "CreatedBy", "UpdatedAt", "UpdatedBy",
    ],
    "Assets": [
        "AssetID", "Timestamp", "User", "AccountID", "Name", "AssetType",
        "Symbol", "Quantity", "Unit", "AvgCost", "CurrentPrice",
        "CurrentValue", "ValuationDate", "IsActive", "LastRebuiltAt",
        "DisposedDate", "SaleProceeds", "RealizedGain",
    ],
    "InvestmentLedger": [
        "TradeID", "WriteBatchID", "Timestamp", "Date", "User", "AssetID",
        "Book", "Side", "Quantity", "UnitPrice", "Fees", "GrossAmount",
        "NetAmount", "AccountID", "LedgerEntryID", "RealizedGain", "Notes",
        "Status", "ReversalOfTradeID",
    ],
    "AssetPrices": [
        "AssetID", "Date", "PricePerUnit", "Source", "UpdatedAt",
    ],
    "PortfolioSnapshots": [
        "Date", "User", "AssetID", "Quantity", "Price", "Value",
        "CostBasis", "UnrealizedGain",
    ],
    "Limits": [
        "LimitID", "User", "Scope", "TargetID", "Period", "Amount",
        "WarnAtPct", "IsActive",
    ],
    "RecurringRules": [
        "RuleID", "User", "Name", "Amount", "AccountID", "CategoryID",
        "Frequency", "NextDueDate", "RemindDaysBefore", "NotifyVia",
        "AutoPost", "IsActive", "LastMatchedEntryID", "LastPaidDate",
        "LastPostedEntryID",
    ],
    "PaymentDefaults": [
        "User", "Method", "DefaultAccountID", "LastUsedAccountID", "IsActive",
    ],
    "NotificationLog": [
        "Timestamp", "User", "Type", "RecordID", "Channel", "Status",
    ],
    "Settings": [
        "User", "Currency", "MonthStartDay", "CardUtilWarnPct",
        "LowLimitFloor", "DefaultBudget", "AlertPrefs", "NotificationEmail",
        "DuplicateWindowDays", "DuplicateDateDays", "DuplicateAmountPct",
        "DuplicateDescriptionPct", "PrivacyToggles",
    ],
    "Audit": [
        "Timestamp", "User", "Action", "Tab", "RecordID", "Before", "After",
        "WriteBatchID",
    ],
    "Valuations": [
        "Date", "User", "CashTotal", "LiabilityTotal", "AssetValue", "NetWorth",
    ],
}

ACCOUNT_KINDS = [
    "savings", "current", "wallet", "cash", "brokerage", "credit_card", "loan",
]

CASH_ACCOUNT_KINDS = ["savings", "current", "wallet", "cash", "brokerage"]

KIND_LABELS = {
    "savings": "Savings",
    "current": "Current",
    "wallet": "Wallet",
    "cash": "Cash",
    "brokerage": "Brokerage",
    "credit_card": "Credit card",
    "loan": "Loan",
}

PAYMENT_METHODS = [
    "upi", "netbanking", "auto_debit", "cheque", "cash", "card", "wallet",
]

METHOD_LABELS = {
    "upi": "UPI",
    "netbanking": "Net banking",
    "auto_debit": "Auto debit",
    "cheque": "Cheque",
    "cash": "Cash",
    "card": "Card",
    "wallet": "Wallet",
    "bill_payment": "Card bill payment",
}

DEFAULT_CATEGORIES = {
    "Expenditure": [
        "Groceries", "Rent", "Utilities", "Transport", "Entertainment",
        "Dining Out", "Shopping", "Health", "Education", "Subscriptions",
        "Fees", "Other",
    ],
    "Income": [
        "Salary", "Interest", "Dividend", "Rental", "Freelance", "Gift",
        "Refund", "Other",
    ],
    "Investment": [
        "Mutual Funds", "Direct Equity", "Bonds", "PPF", "Real Estate",
    ],
}

DEFAULT_SETTINGS = {
    "Currency": "INR",
    "MonthStartDay": 1,
    "CardUtilWarnPct": 30,
    "LowLimitFloor": 0,
    "DefaultBudget": 0,
    "AlertPrefs": "in_app",
    "NotificationEmail": "",
    "DuplicateWindowDays": 45,
    "DuplicateDateDays": 2,
    "DuplicateAmountPct": 2,
    "DuplicateDescriptionPct": 85,
    "PrivacyToggles": "",
}

APP_VERSION = "2.0-data-entry"
SCHEMA_VERSION = "2"
