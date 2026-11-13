# Manual test plan — data-entry build

Use this against the spreadsheets currently configured in `.streamlit/secrets.toml`.
The main pass uses the alias **Main**; §16 switches to a second sheet, alias **Spare**.
Substitute your own alias names if they differ.
Work through the scenarios in order: later balance checks depend on earlier entries.
Run the whole pass in one sitting so all entries fall in the same calendar month.

Every form follows the same contract:

1. Fill the compact form.
2. Press **Review …**.
3. Check the **Confirm** screen.
4. Press **Confirm & save** (or **Save anyway** only when deliberately overriding a duplicate warning), or **Cancel**.

If a step says “cancel”, nothing should be written.

---

## 0. Before you start

### 0.1 Fresh-sheet reset (recommended)

1. Stop Streamlit with `Ctrl+C`.
2. In `.streamlit/secrets.toml`, add a `[spreadsheets]` table with two aliases:

   ```toml
   [spreadsheets]
   Main = "main-spreadsheet-id"
   Spare = "spare-spreadsheet-id"
   ```

   - Share **both** spreadsheets with the service account email (Editor).
   - IDs must be different. IDs never appear in the app; only the aliases do.
   - If a `[spreadsheet]` section is still present, `[spreadsheets]` takes over.
3. Reset **Main**: in Google Sheets keep exactly **one blank tab** (Sheets does not allow zero tabs) and delete every other tab, including `Transactions`, `Investments`, and any `_v1_Accounts`, `_v1_CreditCards`, `_v1_Categories` backups.
   - The `_v1_*` tabs matter: if they remain, bootstrap re-imports their Accounts/Cards into the fresh v2 `Accounts` tab.
   - Cleanest alternative: create brand-new blank spreadsheets for both aliases.
4. **Spare** can also be a single blank tab; leave it untouched for now.
5. Start the app from the repo:

   ```powershell
   py -3 -m streamlit run app.py
   ```

   PowerShell may report exit code 1 for Streamlit bare-mode warnings even when the app is running. Check the browser.

### 0.2 First-run expectations

- [ ] Sidebar shows the logo and **Data source** with the configured aliases. It reads **Main**; no Admin/Sarah/Mike or view-mode controls exist.
- [ ] Sidebar pages are grouped **Capture** (New entry), **Review** (Ledger, Holdings), **Setup** (Accounts & cards, Bills & limits, Settings).
- [ ] The app shows no red bootstrap error.
- [ ] The sheet now has these 17 v2 tabs: `Meta`, `Accounts`, `Categories`, `Tags`, `TagRules`, `Ledger`, `Assets`, `InvestmentLedger`, `AssetPrices`, `PortfolioSnapshots`, `Limits`, `RecurringRules`, `PaymentDefaults`, `NotificationLog`, `Settings`, `Audit`, `Valuations`.
- [ ] `Accounts` has a header but **no data rows** (accounts are never seeded).
- [ ] `Categories` is seeded with 25 rows: 12 Expenditure, 8 Income, 5 Investment.
- [ ] `Tags` is seeded from the lexicon.
- [ ] `Settings` has exactly one row, for owner **Main**.
- [ ] `Meta` shows `SchemaVersion = 2`, `AppVersion = 2.0-data-entry`, a fresh `BootstrappedAt`, `Owner = Main`, and the lexicon version. There is no `Users` row.
- [ ] **Settings → Data & privacy** shows those values, an empty audit trail, and empty/missing legacy backups.
- [ ] **Ledger** says no entries yet. **Accounts & cards**, **Holdings**, **Bills & limits** show empty states.
- [ ] Light theme is active: white background, gray panels, teal/slate accents, dark text.

> Bootstrap is memoized per spreadsheet for the life of the process. After changing aliases/IDs in `secrets.toml`, deleting tabs, or resetting a sheet, fully stop and restart Streamlit.

---

## 1. Canonical test data

Create this data during the pass. Amounts are in rupees; the app stores integer paise.

| Ref | Kind | Data |
|---|---|---|
| A1 | Account | **Salary**, Savings, institution `Bank A`, opening **₹1,00,000.00**, opening date today |
| A2 | Account | **Everyday**, Wallet, institution `Wallet A`, opening **₹5,000.00** |
| A3 | Account | **Cash**, Cash, opening **₹2,000.00** |
| A4 | Account | **Broker**, Brokerage, institution `Broker A`, opening **₹0.00** |
| A5 | Card | **Regalia**, issuer `Bank A`, limit **₹1,00,000.00**, opening outstanding **₹0.00**, statement day skipped (`0`), due day `10` |
| E1 | Expense | **₹1,234.56** from Salary, UPI, description `apples, milk from blinkit`, category Groceries |
| E2 | Expense | **₹5,000.00** from Regalia, method Card, description `laptop stand` |
| I1 | Income | **₹50,000.00** into Salary, category Salary, source `Employer`, TDS **₹5,000.00** (information only) |
| I2 | Income | **₹250.00** into Salary, category Interest, description `Savings interest` |
| T1 | Transfer | **₹10,000.00** Salary → Everyday, Net banking |
| CP1 | Card payment | **₹3,000.00** from Everyday → Regalia, Net banking |
| R1 | Reconcile | Salary actual balance **₹1,38,000.00**, reason `Bank charge`, note `Annual fee`, confirmation ticked |
| T2 | Transfer | **₹25,000.00** Salary → Broker, Net banking |
| SB1 | Stock buy | `NIFTYBEES`, Equity, new holding, symbol `NIFTYBEES`, quantity **10**, unit price **₹200.00**, fees **₹20.00**, paid from Broker |
| V1 | Valuation | NIFTYBEES price **₹220.00** per unit, date today |
| SS1 | Stock sell | NIFTYBEES quantity **4**, total proceeds **₹1,000.00**, fees **₹10.00**, received in Broker |
| SS2 | Stock sell | NIFTYBEES quantity **6**, total proceeds **₹1,500.00**, fees **₹0.00**, received in Broker |
| AB1 | Asset buy | Gold, asset name `Gold 24k`, quantity **10 g**, unit `g`, purchase **₹60,000.00**, fees **₹500.00**, current estimate **₹65,000.00**, paid from Salary |
| AS1 | Asset sell | Gold 24k, quantity **4 g**, proceeds **₹28,000.00**, fees **₹200.00**, received in Salary |
| B1 | Bill | `Internet`, **₹1,000.00**, Everyday, Utilities, monthly, next due today + 7 days, remind 7 days, in app |
| L1 | Limit | Overall, Monthly recurring, **₹20,000.00**, warn 80% |
| L2 | Limit | Category Groceries, Monthly recurring, **₹1,500.00**, warn 80% |
| L3 | Limit | Account Regalia, Monthly recurring, **₹4,000.00**, warn 80% |
| L4 | Limit | Overall, Specific month = previous month, **₹10,000.00**, warn 80% |
| RV1 | Reversal | Reverse **AS1** (gold sale), reason `test reversal` |
| RV2 | Reversal | Reverse **E1** (groceries), reason `test reversal` |

### Checkpoints

| After | Salary | Everyday | Cash | Broker | Regalia balance | Card outstanding | Holdings value | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Accounts only | 1,00,000.00 | 5,000.00 | 2,000.00 | 0.00 | 0.00 | 0.00 | — | Cash & bank ₹1,07,000 |
| E1 | 98,765.44 | 5,000.00 | 2,000.00 | 0.00 | 0.00 | 0.00 | — | |
| E2 | 98,765.44 | 5,000.00 | 2,000.00 | 0.00 | -5,000.00 | 5,000.00 | — | Available limit ₹95,000 |
| I1 + I2 | 1,49,015.44 | 5,000.00 | 2,000.00 | 0.00 | -5,000.00 | 5,000.00 | — | |
| T1 | 1,39,015.44 | 15,000.00 | 2,000.00 | 0.00 | -5,000.00 | 5,000.00 | — | |
| CP1 | 1,39,015.44 | 12,000.00 | 2,000.00 | 0.00 | -2,000.00 | 2,000.00 | — | Available limit ₹98,000 |
| R1 | 1,38,000.00 | 12,000.00 | 2,000.00 | 0.00 | -2,000.00 | 2,000.00 | — | |
| T2 | 1,13,000.00 | 12,000.00 | 2,000.00 | 25,000.00 | -2,000.00 | 2,000.00 | — | |
| SB1 | 1,13,000.00 | 12,000.00 | 2,000.00 | 22,980.00 | -2,000.00 | 2,000.00 | 2,000.00 | Cost ₹2,020; unrealized -₹20 |
| V1 | 1,13,000.00 | 12,000.00 | 2,000.00 | 22,980.00 | -2,000.00 | 2,000.00 | 2,200.00 | Unrealized +₹180 |
| SS1 | 1,13,000.00 | 12,000.00 | 2,000.00 | 23,970.00 | -2,000.00 | 2,000.00 | 1,320.00 | 6 units; realized ₹182 |
| SS2 | 1,13,000.00 | 12,000.00 | 2,000.00 | 25,470.00 | -2,000.00 | 2,000.00 | 0.00 | Stock inactive; realized ₹470 in trade history |
| AB1 | 52,500.00 | 12,000.00 | 2,000.00 | 25,470.00 | -2,000.00 | 2,000.00 | 65,000.00 | Gold cost ₹60,500 |
| AS1 | 80,300.00 | 12,000.00 | 2,000.00 | 25,470.00 | -2,000.00 | 2,000.00 | 39,000.00 | 6 g left; gold realized ₹3,600 |
| RV1 | 52,500.00 | 12,000.00 | 2,000.00 | 25,470.00 | -2,000.00 | 2,000.00 | 65,000.00 | Gold back to 10 g; cost ₹64,500, unrealized +₹500, realized ₹3,600 (see §21) |
| RV2 | 53,734.56 | 12,000.00 | 2,000.00 | 25,470.00 | -2,000.00 | 2,000.00 | 65,000.00 | E1 excluded from spend/limits |

At the **RV2** checkpoint, **Accounts & cards** should show:

- Cash & bank **₹93,204.56**
- Card outstanding **₹2,000.00**
- Available limit **₹98,000.00**
- Loan outstanding **₹0.00**

And **Ledger** should show **15 entries**, **3 transfers**, this month in **₹50,250.00**, this month out **₹65,500.00** (the remaining card expense plus the gold purchase), net **-₹15,250.00**.

---

## 2. Accounts and cards

### 2.1 Create the five accounts

- [ ] **New entry → New account** for A1. Review shows Nickname, Kind, Institution, Currency, opening balance and date. **Confirm & save**; toast “Saved to the ledger.”
- [ ] Repeat for A2, A3, A4.
- [ ] Open **Accounts & cards**. Bank & cash shows all four with current balances. Stats: Cash & bank **₹1,07,000.00**, card outstanding ₹0, available limit ₹0, loan outstanding ₹0.
- [ ] **New entry → New card** for A5. Review shows limit, opening outstanding, available limit ₹1,00,000, statement day “Optional / skipped”, due day 10. Confirm.
- [ ] Accounts & cards now shows Regalia with outstanding ₹0, available ₹1,00,000, **0% utilized**.

### 2.2 Negative checks

- [ ] Try a nickname containing a 16-digit string, e.g. `HDFC 1234567890123456`. **Review account** must show an error: *Nickname looks like an account/card number. Use a nickname only.*
- [ ] Try nickname `Salary` again for a new savings account. **Review account** opens the Confirm screen with **Possible duplicate found** and **Save anyway**. Press **Cancel**; `Accounts` must still contain exactly one Salary row.
- [ ] On the card form, enter limit `0`. Review must error: *Credit limit must be greater than zero.*
- [ ] Try an amount of `0` in an entry form. Review must error: *Amount must be greater than zero.*
- [ ] Future dates: every ledger date picker has `max_value=today`, so a future date cannot be selected. (The service also rejects it if bypassed.)

### 2.3 Sign and edit rules

- [ ] Add a temporary **Loan** account with opening outstanding `₹5,00,000`. Confirm. Accounts & cards must show **Loan outstanding ₹5,00,000** (opening stored as negative).
- [ ] Add a temporary card with opening outstanding `₹15,000` and limit `₹20,000`. Confirm summary shows opening ₹15,000 and available ₹5,000; card block shows outstanding ₹15,000, 75% utilized.
- [ ] Toggle both temporary accounts **Active** off. They disappear from the account/card lists and from Cash & bank/card totals; the rows remain in the sheet with `IsActive = FALSE`.
- [ ] Re-open **Salary → Edit details**, change Institution to `Bank A updated`, **Save details**, then change it back. Toast confirms.
- [ ] Re-open **Regalia → Edit card**, change Due day to `12`, **Save card**, verify the card subtitle shows due day 12, then set it back to `10`.

> Keep only A1–A5 active for the rest of the pass.

---

## 3. Expenses

### 3.1 Confirmation and suggestions

- [ ] **New entry → Expense**. Date today, amount **1234.56**, Paid from **Salary · Savings**.
- [ ] Method `UPI`, description `apples, milk from blinkit`.
- [ ] Confirm the caption says a category was suggested from the description and the Category is **Groceries**. Tags should fill with suggested chips (fruit/milk/Blinkit-style tags, plus the `UPI` method tag). Remove one chip and add it back.
- [ ] Press **Review entry**. Confirm screen shows Date, Amount ₹1,234.56, Paid from, Method UPI, Category Groceries, Tags, Description, Private No.
- [ ] Press **Cancel**. Go to **Ledger**: no expense row was written.
- [ ] Return to New entry. The form keeps the values. Press **Review entry**, then **Confirm & save**.
- [ ] Toast “Saved to the ledger.” Salary becomes **₹98,765.44**.

### 3.2 Duplicate warning

- [ ] Enter the same expense again: same date, amount, account, description. **Review entry**.
- [ ] Confirm screen shows **Possible duplicate found**, a candidate card with date/amount/account/description, and the button changes to **Save anyway**.
- [ ] Press **Cancel**. Only one E1 row exists in `Ledger`.
- [ ] Optional exact-retry/idempotency probe: record a ₹1 cash expense, and on its Confirm screen click **Confirm & save** twice as fast as you can. Expect exactly one Ledger row. The second click may toast *Already saved — no duplicate written.* (the service deduplicates the same `ClientRequestID`). Reverse the probe row in §11 to restore Cash.
- [ ] Optional override check: repeat on a small cash expense (₹10, description `duplicate probe`), press **Save anyway**, and in the sheet verify the second row has a non-empty `DuplicateOfEntryID`. Reverse both probe rows afterwards (see §11).

### 3.3 Card expense

- [ ] Expense **₹5,000.00**, Paid from **Regalia · Credit card**, method `Card`, description `laptop stand`, category Shopping.
- [ ] Review shows Paid from Regalia and method Card. Confirm.
- [ ] Accounts & cards: Regalia outstanding **₹5,000.00**, available **₹95,000.00**, `5% utilized`. No 80% warning at this level.

### 3.4 Optional high-utilization warning

- [ ] Create a temporary card with limit **₹10,000**.
- [ ] Record an **₹8,000** expense on it. The Review screen must show *This expense pushes card utilization above 80%.* Confirm, verify 80% utilization, then reverse the expense and deactivate the card.

> The entry-form threshold is hard-coded at 80%, regardless of the `Card utilization warning %` setting in Preferences.

### 3.5 Category and privacy checks

Do the private-flag, redaction and custom-category entry checks on the **Spare** spreadsheet in §16, not on Main. That keeps Main’s canonical balances and the 15-entry checkpoint exact. Creating `Pets` itself is covered in §14.3; categories are per-spreadsheet, so it does not affect balances.

> Optional tests in §3.2 and §3.4 add extra ledger/reversal rows. The canonical checkpoints assume you cancel those or skip them. If you do override/save and reverse, expect a higher **Entries** count; balances should still match once the reversals are posted.

---

## 4. Income

- [ ] **New entry → Income**, amount **50,000**, Received in **Salary**, Income category **Salary**, Source/payer `Employer`, TDS **5,000**, description `Monthly salary`, Private off.
- [ ] Review shows Net amount ₹50,000, TDS `₹5,000.00 (information only)`. Confirm.
- [ ] Salary becomes **₹1,48,765.44**. `TaxWithheld` in the sheet is `500000`; the balance uses the net amount only.
- [ ] Record I2: **₹250**, category **Interest**, description `Savings interest`. Salary becomes **₹1,49,015.44**.
- [ ] Sheet row description for I1 includes the payer: `Monthly salary — Employer` (payer is appended only if not already present).
- [ ] Duplicate check: repeat I2 with the same date/amount/account/description; warning appears. Cancel.

---

## 5. Transfers

- [ ] **New entry → Transfer**, date today, amount **10,000**, From **Salary**, To **Everyday**, method **Net banking**, note `Move to spending`.
- [ ] Review shows From/To/Method/Note. Confirm.
- [ ] Salary **₹1,39,015.44**, Everyday **₹15,000.00**. Cash & bank total is unchanged at **₹1,56,015.44**.
- [ ] Try From = To = Salary. Review errors: *From and to accounts must be different.*
- [ ] Try the same transfer again. Review warns **Possible duplicate found** (same source, destination and amount within 1 day). Cancel.
- [ ] Ledger: transfer appears with `To / card = Everyday · Wallet`. The Entries hint shows `1 transfers` so far.

---

## 6. Card payments

- [ ] **New entry → Card payment**. Card **Regalia**. The amount prefills with the current outstanding (₹5,000); set it to **3,000**.
- [ ] Pay from **Everyday**, method Net banking. Caption shows current outstanding ₹5,000.
- [ ] Review shows Outstanding before ₹5,000 and outstanding after ₹2,000. Confirm.
- [ ] Everyday becomes **₹12,000.00**; Regalia balance **-₹2,000.00**, outstanding **₹2,000.00**, available **₹98,000.00**.
- [ ] The “Pay from” list contains only bank/wallet/cash accounts, never a credit card.
- [ ] Optional overpayment: pay ₹3,000 more. Regalia balance becomes positive; outstanding displays **₹0.00** (a credit balance is not shown as negative outstanding). Reverse this payment afterwards if you want the canonical checkpoint restored.

---

## 7. Reconcile

- [ ] **New entry → Reconcile**, account **Salary**. App balance should show **₹1,39,015.44**.
- [ ] Enter Actual balance **1,38,000**, reason **Bank charge**, note `Annual fee`. Do **not** tick the confirmation checkbox; Review must error: *Tick the confirmation checkbox first.*
- [ ] Tick **I understand this writes a permanent adjustment**, then Review.
- [ ] Summary shows App balance ₹1,39,015.44, Actual ₹1,38,000, Adjustment **-₹1,015.44**. Confirm.
- [ ] Salary becomes **₹1,38,000.00**. Ledger row type **Reconcile**, amount `-₹1,015.44`.
- [ ] Review again with the same actual balance. Error: *Actual balance already matches. Nothing to reconcile.*
- [ ] Optional card reconcile: set Regalia actual outstanding to ₹2,500. Summary adjustment is **-₹500.00**; after saving, outstanding is ₹2,500. Reverse it if following the canonical numbers.

---

## 8. Stock / mutual-fund trades

### 8.1 Buy

- [ ] Transfer **₹25,000** Salary → Broker (T2). Salary **₹1,13,000.00**, Broker **₹25,000.00**.
- [ ] **New entry → Stock buy**. Paid from **Broker**, Holding **New holding**, Asset type **Equity**.
- [ ] Name `NIFTYBEES`, Symbol `NIFTYBEES`, Unit `units`, Quantity **10**, Unit price **200**, Fees **20**, Notes `First lot`.
- [ ] Review shows Gross ₹2,000, Fees ₹20, Cash out **₹2,020**, Paid from Broker. Confirm.
- [ ] Broker becomes **₹22,980.00**. **Holdings → Investments** shows NIFTYBEES, 10 units, value ₹2,000, price ₹200/unit, unrealized **-₹20.00**. Open **Update valuation** to see the cost basis ₹2,020.
- [ ] **Holdings → Trade history** shows one **Buy**, status Posted, net ₹2,020.

### 8.2 Valuation

- [ ] On the NIFTYBEES holding, open **Update valuation**, price **220**, date today, **Review valuation**.
- [ ] Confirm summary shows new price ₹220 and new value ₹2,200. Confirm.
- [ ] Holding value **₹2,200.00**, unrealized **+₹180.00**. `AssetPrices` gains a manual row.

### 8.3 Partial sell

- [ ] **New entry → Stock sell**. Holding NIFTYBEES. The form prefills quantity 10 and proceeds ₹2,200 (held × current price); set quantity **4**, proceeds **1,000**, fees **10**, received in **Broker**.
- [ ] Note the Quantity sold input is capped at the held amount, so the form cannot oversell; the service also rejects quantity > held.
- [ ] Review shows quantity 4 units, proceeds ₹1,000, fees ₹10, net received ₹990, cost basis ₹808, realized gain **+₹182.00**. Confirm.
- [ ] Broker **₹23,970.00**. Holding: 6 units, value **₹1,320.00**, realized ₹182 in trade history.
- [ ] Ledger has a `stock_sell` row of ₹990 (net cash), not ₹1,000.

### 8.4 Full exit

- [ ] Stock sell the remaining **6** units, proceeds **1,500**, fees **0**, into Broker.
- [ ] Review: cost basis ₹1,212, realized **+₹288.00**. Confirm.
- [ ] Broker **₹25,470.00**. The holding disappears from **Investments** (IsActive FALSE, quantity 0).
- [ ] Trade history still shows all three trades; realized column shows +₹182 and +₹288 (total ₹470).

> Known behavior: the Holdings **Realized** tile sums only active holdings. A fully exited position’s realized gain stays in Trade history but drops off the tile. Confirm this matches your intent before changing it later.

---

## 9. Physical assets

### 9.1 Buy

- [ ] **New entry → Asset buy**. Asset type **Gold**, name `Gold 24k`, quantity **10**, unit `g`.
- [ ] Purchase price **60,000**, fees **500**, current estimated value **65,000**, paid from **Salary**, notes `24k coins`.
- [ ] Review shows purchase ₹60,000, fees ₹500, cash out **₹60,500**, unit cost ₹6,000, current value ₹65,000. Confirm.
- [ ] Salary **₹52,500.00**. **Holdings → Physical assets** shows Gold 24k, 10 g, value **₹65,000**, price ₹6,500/g, unrealized **+₹4,500.00**. Open **Update valuation** to see the cost basis ₹60,500.
- [ ] Ledger type **Asset buy**, amount ₹60,500, paid from Salary.

### 9.2 Sell

- [ ] **New entry → Asset sell**. Asset `Gold 24k`, quantity **4 g**, proceeds **28,000**, fees **200**, received in **Salary**.
- [ ] Review: net received ₹27,800, cost basis ₹24,200, realized gain **+₹3,600.00**. Confirm.
- [ ] Salary **₹80,300.00**. Holding: 6 g, value **₹39,000**, unrealized **+₹2,700**; Trade history shows realized ₹3,600.
- [ ] Ledger type **Asset sell**, amount ₹27,800 (net), received in Salary.

### 9.3 Rebuild cache

- [ ] **Holdings → Maintenance → Rebuild holdings from trade history**. Toast reports the number of holdings and trades rebuilt.
- [ ] Gold remains 6 g, value ₹39,000; the sheet (or the Asset sell form caption) still shows avg cost ₹6,050. Stock remains inactive. Nothing changes.

---

## 10. Limits

Create these **before doing the reversals**, so you can see the pre-reversal percentages. Limits are read-only reporting; they never block an entry.

Open **Bills & limits → Add limit** for L1–L4.

- [ ] L1 Overall / Monthly recurring / ₹20,000 / 80%. Confirm. Limit card shows spent **₹6,234.56**, **31% used**, remaining money and a progress bar.
- [ ] L2 Category Groceries / Monthly recurring / ₹1,500 / 80%. Spent **₹1,234.56**, about **82% used**, caption *Close to limit · ₹265.44 left.*
- [ ] L3 Account Regalia / Monthly recurring / ₹4,000 / 80%. Spent **₹5,000**, **125% used**, caption *Over limit by ₹1,000.00.*
- [ ] L4 Overall / Specific month = previous month / ₹10,000 / 80%. Spent **₹0**, 0% used. The period label shows the stored `YYYY-MM`.
- [ ] Try amount **0**. Review errors: *Limit must be greater than zero.*
- [ ] Limits never block an expense; they only display progress and warnings.
- [ ] Toggle L4 **Active** off. The card remains but its toggle is off; **Active limits** decreases by 1 and **Over limit** ignores it.
- [ ] `Limits` sheet rows have `Scope`, `TargetID`, `Period` (`monthly` or `month:YYYY-MM`), integer `Amount`, `WarnAtPct`, `IsActive`.
- [ ] After the grocery reversal in §11.2, L2 returns to 0%, L1 drops to ₹5,000, L3 stays ₹5,000. Verify on a refresh/rerun.

> Limits count only `expense` rows in the current calendar month. Stock/asset purchases and reversals are excluded. `MonthStartDay` is not applied here yet.

---

## 11. Reversals

### 11.1 Reverse the gold sale

- [ ] **Ledger → Reverse an entry**. Select the **Asset sell** row for Gold 24k (amount ₹27,800).
- [ ] Summary shows Date, Type Asset sell, Amount, Account, Category, Description, Status Posted.
- [ ] Enter reason `test reversal`, reversal date today, **Review reversal**, then **Confirm & save**.
- [ ] Ledger now has the original and a mirrored **Reversal** row; both remain. Original is locked.
- [ ] Salary returns to **₹52,500.00**. Gold returns to **10 g**, value **₹65,000**; the automatic rebuild has already run. Run **Rebuild** again to verify stability.
- [ ] Actual rebuilt holding after the reversal: unrealized **+₹500** on the block; the sheet (or sell form) shows average cost **₹6,450**, cost basis **₹64,500**, realized **₹3,600**. This is not a full accounting reversal; see §21.
- [ ] Trade history shows the original sell and a reversal trade (side **Buy**, `RealizedGain` **-₹3,600**, `ReversalOfTradeID` set).

### 11.2 Reverse the grocery expense

- [ ] Reverse **E1** (`apples, milk from blinkit`, ₹1,234.56) with reason `test reversal`.
- [ ] Salary becomes **₹53,734.56**. Ledger has 15 entries.
- [ ] E1 is excluded from **This month out** and from limit spend: overall limit spent drops from ₹6,234.56 to ₹5,000; Groceries limit drops to 0%.
- [ ] Try to reverse the reversal: reversal rows do not appear in the dropdown. Reversed originals do not appear either.

### 11.3 Optional transfer reversal

- [ ] Reverse a transfer (e.g. T2 Salary → Broker). Both account balances must revert: Salary +₹25,000, Broker -₹25,000. Reverse the reversal is impossible. This is optional because it breaks the canonical checkpoints.

---

## 12. Bills and reminders

- [ ] **Bills & limits → Add bill** for B1: Internet, ₹1,000, Everyday, Utilities, monthly, next due today + 7, remind 7, in app, Active.
- [ ] Review shows Name, Amount, Account, Category, Frequency, Next due, Remind, Notify, Active. Confirm.
- [ ] Try Review with blank name, zero amount, or (when no account exists) no account; expect *Bill name is required*, *Amount must be greater than zero*, or *Choose an account or card*.
- [ ] **Bills** tab shows the card with amount ₹1,000, next due date and *in 7d*; caption shows remind 7 days and in app.
- [ ] **New entry** and **Ledger** show an **Upcoming** strip with `Internet · in 7d`.
- [ ] Stats: Active bills 1, Due in 7 days ₹1,000 with hint *1 reminder(s)*.
- [ ] Press **Mark paid**. Toast “Moved to the next cycle.” Next due advances one month from the stored due date, not from today.
- [ ] **No Ledger row is created**; bills are reminders only. `RecurringRules.AutoPost` stays FALSE and `LastPaidDate` is set.
- [ ] Toggle the bill **Active** off. It stays visible with the toggle off, disappears from the Upcoming strip, and Active bills drops to 0. Toggle it back on.
- [ ] Optional date-clamp check: create a monthly bill due **2027-01-31**, Mark paid, verify next due **2027-02-28** (day clamped to 28). Deactivate this test bill.
- [ ] Optional overdue check: create a bill due yesterday. Bills page shows *overdue by 1d*. The New entry/Ledger strip currently renders it as `in -1d` — note this as a display quirk, not a blocker.
- [ ] Future dates are allowed for bills (unlike ledger entries). Create a bill due next year and confirm it saves; deactivate it afterwards.

---

## 13. Ledger review, filters and totals

- [ ] **Ledger** stats now: This month in **₹50,250.00**, This month out **₹65,500.00** (the remaining card expense plus the gold purchase), Net **-₹15,250.00**, Entries **15**, hint `3 transfers`.
  - If you opened Ledger before the reversals, it should have shown out ₹66,734.56, Net -₹16,484.56 and Entries 13. The two reversals remove E1 from the totals and add two Reversal rows.
- [ ] **Filters → Search description** `apples` finds E1 before the reversal; after RV2 it also finds the reversal row (description `Reversal: apples, milk from blinkit`), while spend totals still exclude the reversed E1.
- [ ] Type filter `Expense` shows only expenses (and not transfers/trades). Clear it.
- [ ] Date range: default From = today - 90 days, To = today. Set From/To to exclude entries; table shows “No entries match these filters.” Tick **All time** to restore.
- [ ] Table columns: Date, Type, Amount, Fees, Account, To / card, Category, Description, Tags, Status, Private. Amounts use Indian grouping (`₹1,23,456.78`).
- [ ] Transfers show both Account and To / card. Stock/asset trades show the cash amount, not the gross trade value.
- [ ] Expand **Legacy data (read-only, not imported)**. On a fresh sheet it shows `Transactions: empty` and `Investments: empty` (or missing); nothing is imported.

---

## 14. Settings, defaults and categories

### 14.1 Preferences

- [ ] **Settings → Preferences**. Change Month starts on day to `25`, Card utilization warning % to `50`, Duplicate protection → Window (days) to `30`, Date tolerance (days) to `1`, Amount tolerance % to `1.0`, Description similarity % to `90`, Low balance floor to `1,000`, Default monthly budget to `25,000`, Alerts to `Both`, Notification email to a test address. **Save preferences**.
- [ ] Reload the page (or restart): values persist. `Settings` has one row for the active alias, and it is the row that changed.
- [ ] Change them back to defaults: Month start 1, Card util 30, Window 45, date tolerance 2, amount tolerance 2.0, description 85, floors 0, default budget 0, alerts In app, email blank. Save.

> Known gaps: `MonthStartDay` is stored but “This month” still uses the calendar month; the entry-form card warning is hard-coded at 80%; Currency is informational and amounts always render with ₹.

### 14.2 Payment defaults

- [ ] **Settings → Payment defaults**: set UPI → Salary, Net banking → Salary, Card → Regalia, Card bill payment → Everyday, Cash → Cash, Wallet → Everyday. **Save defaults**.
- [ ] New entry → Expense: Paid from prefills **Salary** for UPI. Change to Regalia and note the method flips to Card and tags re-suggest.
- [ ] Transfer: From prefills Salary; Card payment: Pay from prefills Everyday.
- [ ] Defaults only prefill. Every entry still requires **Review → Confirm & save**.
- [ ] Clear all defaults back to `— none —` if you want the next pass to use first-account fallbacks.

### 14.3 Categories

- [ ] **Settings → Categories**. Expenditure shows the 12 seeded categories plus `Pets` (26 total across types = 25 seeds + Pets).
- [ ] Untick `Pets`. It disappears from the expense Category dropdown on New entry. Existing ledger rows still display `Pets` via the category map (inactive categories remain readable).
- [ ] Re-tick `Pets`. Add a category `Insurance` under Expenditure; verify it appears in the dropdown.
- [ ] Categories are per-spreadsheet reference data: switch to Spare in §16 and confirm it has its own seeded list without `Pets` or `Insurance`. Switch back and the Main list is unchanged.

---

## 15. Privacy, audit and cache

- [ ] **Settings → Data & privacy** summary shows Schema `2`, App `2.0-data-entry`, a recent Bootstrapped timestamp, Lexicon version, Legacy backups (empty on a fresh sheet), and `Owner = Main`.
- [ ] **Audit trail** is newest-first, max 25 rows, for the active spreadsheet only, with columns When, Action, Tab, Record and Batch. Expect actions such as `post_expense`, `post_income`, `post_transfer`, `card_payment`, `reconcile`, `buy_asset`, `sell_asset`, `reverse_entry`.
- [ ] Pick an audit row and check the corresponding `Ledger` row has the same `WriteBatchID` as its Batch value. Trade batches show `Ledger+InvestmentLedger`.
- [ ] **Refresh cached reads**: in Google Sheets, edit a harmless field, e.g. change Cash account `Notes` to `cache test`. Back in the app press **Refresh cached reads**, then open Accounts & cards → Cash → Edit details. The note updates. Restore the note and refresh once more.
  - Do this sparingly; Google Sheets read quota is small. Never edit IDs or amounts directly.
- [ ] In the sheet, search Ledger/Assets/InvestmentLedger/RecurringRules for digit strings of 10+ characters. Only opaque IDs and integer amounts should appear; no account/card numbers.

---

## 16. Spreadsheet switching and isolation

Prerequisite: **Main** and **Spare** are both configured in `[spreadsheets]` (§0.1) and the app was restarted after adding them.

### 16.1 Confirm before switching

- [ ] Sidebar **Data source** shows only aliases; no spreadsheet ID appears anywhere in the app.
- [ ] Select **Spare** but press nothing. The caption says *Reading Main until you confirm the switch.* Pages still show Main data.
- [ ] Press **Keep current**. The dropdown returns to Main; nothing reloads or changes.
- [ ] Select **Spare** → **Confirm switch**. A spinner runs, then the caption says *Reading only Spare*.
- [ ] Spare is bootstrapped on its first switch: 17 tabs, 25 categories, tags, and one `Settings` row for owner `Spare`. `Meta` has `Owner = Spare` and no `Users`.
- [ ] Accounts, Ledger, Holdings and Bills are empty on Spare. Main’s accounts and entries must not appear.
- [ ] Switch back to Main. Main’s data is exactly as before; Spare’s rows are absent.

### 16.2 Pending confirmation is discarded on switch

- [ ] On Main, open New entry → Expense, fill a small amount, press **Review entry** so the confirmation screen is showing. Do not confirm.
- [ ] Switch to Spare and press **Confirm switch**. The pending confirmation disappears with no write.
- [ ] Main’s Ledger still has no new row for that abandoned entry (the 15-entry checkpoint stays exact).

### 16.3 Isolation checks on Spare

- [ ] Create account `Spare Wallet` (Wallet, opening ₹1,000).
- [ ] Record a **₹100** expense from Spare Wallet, category **Groceries**, description `pet food`, **Private** ticked. Ledger shows `Private = Yes` (privacy is still display-only).
- [ ] Record a **₹50** expense from Spare Wallet with description `Paid card 1234 5678 9012 3456`. After saving, the Ledger/sheet description is `Paid card [redacted]`; no card number is persisted.
- [ ] Record **₹500** income into Spare Wallet. Spare Wallet balance is **₹1,350.00**.
- [ ] Spare’s Audit trail contains only the Spare batches; Main’s audit rows are not shown.
- [ ] Switch back to Main and confirm Main’s audit trail and balances are unchanged. Main’s categories still include `Pets` and `Insurance`.

### 16.4 Failed switch (optional, needs a bad ID)

- [ ] Stop Streamlit. Add a third alias whose ID the service account cannot open (for example a deleted sheet), restart, select it, and press **Confirm switch**.
- [ ] The sidebar shows *Could not open that spreadsheet. Staying on the current sheet.* The current alias stays active and pages remain usable.
- [ ] Remove the bad alias and restart to return to the two-sheet setup.

---

## 17. Theme, layout and responsiveness

- [ ] Entire app is white / gray: white background, `#fafafa`/`#f4f4f5` panels, `#e4e4e7`/`#ededf0` borders, `#27272a` text, `#71717a` muted text.
- [ ] Accents are only teal (`#0f766e`) or slate (`#334155`); no blue/purple/orange except the primary button.
- [ ] Primary buttons (**Review entry**, **Confirm & save**, **Save preferences**, etc.) are `#27B4F5` with a `#149bdb` border and dark-gray text. Hover darkens to `#1ba7e6` / `#118fc9`.
- [ ] Native Streamlit controls (sidebar, tabs, toggles, dataframe) follow the light theme from `.streamlit/config.toml`.
- [ ] At a narrow browser width, the entry columns stack without horizontal scrolling; forms remain usable.
- [ ] Google Fonts load; numbers use the mono style; the logo is teal/dark and readable in the sidebar.
- [ ] Browser console has no uncaught errors. (Streamlit may log harmless warnings.)
- [ ] All color overrides live in the `:root` token block in `src/ui/theme.py`; changing a token there changes the app without touching component code.

---

## 18. Sheet-level integrity

Open the spreadsheet and spot-check:

- [ ] `Ledger` has exactly the 24 schema columns; every test row has a unique `EntryID`, a `ClientRequestID`, a `WriteBatchID`, `Status = posted`, ISO `Date`, and integer-paise `Amount`.
- [ ] Original rows stay present after reversal; reversal rows have `Type = reversal`, `LinkedEntryID` pointing at the original, and mirrored amounts/effects.
- [ ] `DuplicateOfEntryID` is set only on deliberately overridden duplicates.
- [ ] `InvestmentLedger` rows link back through `LedgerEntryID`; `Status = posted`; stock buys/sells use Book `investment`, gold uses `physical`; the reversal trade has `ReversalOfTradeID`.
- [ ] `Assets` matches a rebuild: quantities, average cost, current price/value, realized gain; fully exited stock has `IsActive = FALSE`, quantity 0, `DisposedDate` set.
- [ ] `AssetPrices` has manual valuation rows. `PortfolioSnapshots` and `Valuations` are empty (dashboards deferred).
- [ ] `RecurringRules` has `AutoPost = FALSE` for every bill; `NotificationLog` stays empty (no notifications are sent).
- [ ] `Limits` amounts are paise; `PaymentDefaults` has at most one row per user/method.
- [ ] `Settings` has one row for the active alias; `Audit` has one row per committed ledger/trade batch (reversals included). Account/card edits, bill/limit saves and settings changes are not audited in this build.
- [ ] `Meta` has `Owner` set to the active alias (no `Users` row) and values fresh and consistent with the app; `_v1_*` tabs are absent on a fresh sheet.
- [ ] No account/card numbers, CVVs, PINs or long digit strings exist anywhere outside opaque IDs/amounts.

---

## 19. Reset after testing

The app is append-only; there is no delete button.

1. Stop Streamlit.
2. Either point the alias at a new blank spreadsheet in `.streamlit/secrets.toml`, or in the test sheet:
   - keep one blank tab;
   - delete all other tabs, including `_v1_Accounts`, `_v1_CreditCards`, `_v1_Categories`;
   - optionally keep the legacy `Transactions`/`Investments` tabs if you want to inspect them, but they are not used by v2.
3. Restart `py -3 -m streamlit run app.py`.
4. Confirm the §0.2 first-run expectations again. Bootstrap seeds Categories, Tags and Settings; it does **not** create accounts.

If you only clear v2 rows but leave `_v1_*` tabs, bootstrap may re-import legacy accounts/cards. Delete the backups for a true reset.

---

## 20. Quick smoke path (10 minutes)

If you only want a fast confidence check, do this subset and verify the arithmetic:

1. Create `Salary` savings with opening **₹100,000** and `Everyday` wallet with **₹5,000**.
2. Expense **₹1,000** from Salary → Salary **₹99,000**.
3. Income **₹5,000** into Salary → **₹1,04,000**.
4. Transfer **₹2,000** Salary → Everyday → Salary **₹1,02,000**, Everyday **₹7,000**.
5. Create card `Test Card` limit **₹10,000**, opening 0.
6. Card expense **₹1,000** → outstanding **₹1,000**.
7. Card payment **₹500** from Everyday → Everyday **₹6,500**, outstanding **₹500**.
8. Reconcile Salary to **₹1,01,500** (adjustment -₹500) → Salary **₹1,01,500**.
9. Reverse the ₹1,000 expense (reason `smoke test`) → Salary **₹1,02,500**, expense excluded from month totals.
10. Add an overall monthly limit **₹5,000** → spent **₹1,000** (the card expense), 20% used.
11. Add a bill **₹500** due in 7 days → appears in the Upcoming strip; Mark paid advances it one month; no Ledger row is created.

Final quick-path balances: Salary **₹1,02,500**, Everyday **₹6,500**, Test Card outstanding **₹500**.

---

## 21. Known gaps and observations (confirm before treating as failures)

These are current behaviours found in the code, not test-script mistakes.

1. **Asset/trade reversal is only a cash + quantity reversal.** `reverse_entry` writes the mirrored ledger row and an opposite-side trade, then rebuilds. For the gold sale in §11.1:
   - cash and quantity are correct;
   - the reversal trade is treated as a fresh **buy at the sale price**, so cost basis becomes ₹64,500 instead of returning to ₹60,500;
   - realized gain stays ₹3,600 in the rebuilt holding even though the reversal row has `RealizedGain = -3,600`;
   - `SaleProceeds` is not reduced.

   The Trade history rows look right, but the `Assets` cache does not fully restore the pre-sale cost/realized state. Decide whether reversal should restore the original cost basis before relying on it for tax/realized-gain reporting.

2. **Holdings “Realized” tile only sums active holdings.** A fully exited stock’s realized gain remains in Trade history but drops off the tile once the holding is inactive. At the SS2 checkpoint the tile is ₹0 while the trade rows total ₹470.

3. **Overdue bills in the top strip** render as `in -Nd`; the Bills page correctly says `overdue by Nd`. Cosmetic only.

4. **`MonthStartDay` is stored but not used** by Ledger “This month” or limit periods; both use the calendar month.

5. **The card-utilization preference is stored but not used** by the entry warning (hard-coded 80%) or the account/card colour bands (hard-coded 50/80).

6. **An alias is the owner.** Renaming an alias in `secrets.toml` changes the `User` the app looks for, so rows written under the old alias disappear from the UI even though they remain in the sheet. Keep aliases stable, or plan a re-label before renaming.

7. **Existing rows with old user names are not re-labelled.** Only legacy Accounts/Cards migrated by bootstrap are stamped with the new alias. Ledger/trade rows previously written as `Admin (Master)`, `Sarah` or `Mike` stay in the sheet but are ignored by every query until migrated or reset. This is why a fresh sheet is recommended for this pass.

8. **Ledger monthly “out” includes `asset_purchase`** but excludes stock/asset sales, stock buys and transfers. Confirm that matches how you want spending measured; the tax/portfolio views are not built yet.

9. **Currency is informational.** `Currency` is stored, but money is always formatted with `₹`.

10. **Bills are reminders only.** Mark paid advances `NextDueDate`; it does not create an expense. No notification is sent to email/in-app channels yet.

11. **No delete or hand-edit UI for ledger rows.** Corrections must go through Reconcile or Reversal; this is intentional for the append-only design.

12. **Bootstrap is per process and per spreadsheet.** Changing aliases, IDs or sheet tabs requires a full Streamlit restart, otherwise the cached workbook/bootstrap for the old sheet is reused.

