# Data Entry v2 — implementation plan

> Goal: a fast, compact, OpenCode-style entry app that safely writes to Google
> Sheets. Dashboards and charts are explicitly **out of scope** for this gate.

## Acceptance criteria

- Entry forms exist for: expense, income, transfer, card payment, stock/MF buy
  and sell, physical asset buy and sell, reconcile, new account, new card,
  recurring bill, spending limit, payment default, and reverse entry.
- Every write is confirmed by a compact summary before it reaches Sheets.
- Double submits write one row; near-duplicates show a warning with a
  save-anyway override.
- Account/card dropdowns come from `Accounts`; no identifiers are stored.
- Stock/MF trades write a cash row and a separate trade row; `Assets` is the
  current holding cache.
- Existing v1 tabs are backed up before `Accounts` / `Categories` are rewritten.
- The UI uses Google Fonts, is compact, and stacks cleanly on small screens.
- Import/compile checks and core unit tests pass.

## Steps

1. **Foundation**
   - Add v2 tab schemas (`Meta`, `Ledger`, `Accounts`, `Categories`, `Tags`,
     `TagRules`, `Assets`, `InvestmentLedger`, `AssetPrices`,
     `PortfolioSnapshots`, `Limits`, `RecurringRules`, `PaymentDefaults`,
     `NotificationLog`, `Settings`, `Audit`, `Valuations`).
   - Idempotent bootstrap: back up v1 tabs, migrate legacy rows, seed
     categories/tags/settings, record schema version.
2. **Repository and utilities**
   - Sheet read/append/update helpers, caching, cache invalidation.
   - Integer-paise money helpers, Indian formatting, opaque IDs, text privacy.
3. **Services**
   - Accounts/cards, categories, ledger posting/reversal/balance derivation.
   - Assets and trade ledger, duplicate detection, tag suggestions, defaults,
     recurring rules and limits.
4. **UI shell**
   - Light neutral theme, Inter + JetBrains Mono, compact max-width,
     responsive CSS, sidebar navigation and spreadsheet selector (aliases only).
5. **Entry experience**
   - Type pills → compact form → confirm summary → save.
   - Suggested tags/category, editable chips, duplicate warning, save-anyway.
6. **Management screens**
   - Accounts & cards, ledger + reverse, assets/valuation, bills & limits,
     settings/defaults/categories.
7. **Verification**
   - `python -m compileall`, unit tests for money/signs/duplicates/tagging,
     boot the app headlessly and check for import/runtime errors.

## Rollback

- Every legacy tab is copied to `_v1_<name>` before migration.
- New tabs are additive; the old `Transactions` / `Investments` tabs are kept.
- No delete API is used by the app.
