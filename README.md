# 💸 Ledger — data-entry build

A compact Streamlit finance tracker backed by one or more Google Sheets. Each
spreadsheet is a single append-only ledger with one owner; the sidebar switches
between spreadsheets by alias only. Spreadsheet IDs never appear in the UI.

## Features

- **Fast data entry:** expense, income, transfer, card payment, stock/asset buy
  and sell, reconcile, new account/card, limit and bill forms.
- **Confirm before writing:** every form ends on a summary screen; nothing is
  written until **Confirm & save**. Near-duplicates warn and can be overridden;
  exact retries are idempotent.
- **Append-only ledger:** integer paise amounts, derived balances, audited
  reversals. No delete or hand-edit UI.
- **Trade history kept separate:** stock/MF/ETF and gold trades live in
  `InvestmentLedger`; the matching cash movement lives in `Ledger`.
- **Bills are reminders:** recurring bills never auto-post. Future dates are
  allowed for bills only; ledger dates are capped at today.
- **Multiple spreadsheets, one owner each:** add any number of
  `alias = "spreadsheet-id"` pairs in `secrets.toml`. The selected alias is also
  the owner written in the `User` column.
- **Light, compact UI:** white/gray surface, teal or slate accents, responsive
  columns and Google Fonts.

Dashboards and aggregation are intentionally deferred until data entry has been
manually tested.

## Setup

1. Create a Google Cloud service account, enable the Google Sheets API, and share
   each target spreadsheet with the service account email (Editor).
2. Create `.streamlit/secrets.toml` (never commit it):

   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "..."
   client_id = "..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "..."
   universe_domain = "googleapis.com"

   [spreadsheets]
   Home = "1AbC...spreadsheet-id..."
   Business = "9XyZ...spreadsheet-id..."
   ```

   - Keys under `[spreadsheets]` are the aliases shown in the app. Use plain
     display names; quote aliases that contain spaces or punctuation.
   - Every ID must be unique. Each spreadsheet holds one owner, so do not point
     two aliases at the same sheet.
   - The old single-sheet layout (`[spreadsheet] id = "..."`) still works and is
     shown as the alias **Default sheet** until you add `[spreadsheets]`.

3. Install and run:

   ```powershell
   py -3 -m pip install -r requirements.txt
   py -3 -m streamlit run app.py
   ```

On first run the app seeds the required tabs, categories, tags and one owner
settings row. It never overwrites tabs that already contain data. The first
sheet listed under `[spreadsheets]` is selected initially.

## Switching spreadsheets

1. Pick an alias in the sidebar.
2. Press **Confirm switch**. Until then the current sheet stays active.
3. The app bootstraps the new sheet (if needed), clears cached reads, and reads
   only that sheet. Unconfirmed entry plans are discarded because they belong to
   the old sheet.

A failed switch keeps the previous alias active. Bootstrap is memoized per
spreadsheet for the life of the process, so restart Streamlit after deleting
tabs or changing aliases.

Every alias is separate data: accounts, ledger rows, limits, bills, settings,
payment defaults and audit rows are not shared between spreadsheets. Category
and tag seeds are per sheet.

## Data safety

- Only nicknames and opaque generated IDs are stored. The app rejects
  account-number-like nicknames and redacts card-like digit strings in free text.
- Amounts are stored as integer paise. Balances are derived from the ledger.
- Corrections use **Reconcile** or **Reversal**; both are audited.
- Bootstrap copies legacy v1 tabs to `_v1_*` before migrating. Delete those
  backups only when you want a true reset.

## Sheet tabs

`Meta`, `Accounts`, `Categories`, `Tags`, `TagRules`, `Ledger`, `Assets`,
`InvestmentLedger`, `AssetPrices`, `PortfolioSnapshots`, `Limits`,
`RecurringRules`, `PaymentDefaults`, `NotificationLog`, `Settings`, `Audit`,
`Valuations`.

Legacy `Transactions` and `Investments` tabs are preserved read-only and are not
imported. Dashboards, portfolio snapshots and notifications are not built yet;
see `MANUAL_TEST_PLAN.md` for current behaviour and known gaps.

## Project layout

```text
finance_tracker/
├── .streamlit/
│   ├── config.toml              # light theme + server settings
│   └── secrets.toml             # service account + [spreadsheets] (git-ignored)
├── app.py                       # entry point, navigation, startup
├── assets/                      # logo and static assets
├── MANUAL_TEST_PLAN.md          # end-to-end manual test scenarios
├── src/
│   ├── data_sources.py          # alias -> ID parsing and session state
│   ├── source_selector.py       # sidebar selector and confirmed switch
│   ├── config.py                # account types and legacy sheet schemas
│   ├── data/                    # lexicon for tag suggestions
│   ├── db/
│   │   ├── repo.py              # typed Google Sheets repository + caches
│   │   ├── schemas.py           # v2 tab schemas and defaults
│   │   └── bootstrap.py         # idempotent setup and v1 migration
│   ├── services/                # accounts, ledger, assets, limits, bills, ...
│   ├── ui/
│   │   ├── theme.py             # :root color tokens and global CSS
│   │   ├── components.py        # shared layout helpers
│   │   └── pages/               # entry, ledger, holdings, accounts, bills, settings
│   └── utils/                   # ids, money, privacy
└── requirements.txt
```

`src/analytics.py`, `src/database.py` and `src/components/` are v1 leftovers and
are not used by the current app.
