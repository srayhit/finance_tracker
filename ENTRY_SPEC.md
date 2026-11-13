# Entry Specification — what the user types, per entry type

> Review document. Each section proposes the fields the user should fill in,
> what the app derives automatically, and what gets written. Mark changes
> inline or reply with the section numbers. **Nothing here stores account or
> card numbers.**

Legend: **R** = required · **O** = optional · **A** = auto/derived (not typed)

---

## 0. Global rules (apply to every entry)

| Rule | Suggestion |
|---|---|
| Date | Default **today**; allow past dates; block future dates for ledger entries. Future dates are allowed only for bills/reminders. |
| Amount | > 0, two decimals, stored as integer paise. |
| Account list | Only **active** accounts the user owns (or shared household accounts, if enabled). |
| Category list | Only active categories of the matching type; "＋ New category" inline. |
| Default accounts | Per-payment-method defaults (UPI → Savings, card bill → Savings, etc.) prefill the source account. The source is always visible and editable. |
| Account/card dropdowns | Read live from `Accounts` (cards are `Kind = credit_card`). Label `Nickname — Kind`; value is the internal `AccountID`. Never a number. |
| Confirmation step | Every entry shows a final summary (date, amount, source/destination, method, category/tags) with **Confirm / Cancel** before writing. The default never bypasses confirmation. |
| Idempotent submit | Each rendered form gets a `ClientRequestID`. A repeated submit returns the existing entry instead of writing a second one. |
| Duplicate warning | Same or near-same entries show a side-by-side candidate panel before saving. Saving anyway records `DuplicateOfEntryID` + an audit override. |
| Description | Optional, max ~120 chars, sanitized by `privacy.sanitize_free_text()`. |
| Private | Checkbox, default **off**. Hidden from other household members in Combined view. Only meaningful on ledger entries. |
| Currency | Default from user settings (INR). |
| Never asked | Account number, card/PAN number, CVV, expiry, IFSC, UPI ID, PIN, customer ID. |

### 0a. Payment defaults (prefill, always confirm)

| Context | Prefilled source | Notes |
|---|---|---|
| Expense via UPI | Default UPI account (e.g. Savings) | method tag `upi` |
| Expense via card | Last-used card | card outstanding increases |
| Expense via netbanking / auto-debit / cheque / cash | Default account for that method | method tag added |
| Card bill payment | Default bill-pay account (e.g. Savings) | card outstanding decreases |
| Internal transfer | Last-used "from" account | user can change |

Stored in **`PaymentDefaults`**: `User`, `Method` (upi/netbanking/
auto_debit/cheque/cash/card/bill_payment), `DefaultAccountID`,
`LastUsedAccountID`, `IsActive`. Fallback order: explicit default → last used →
first active account. The final confirmation summary always shows the resolved
account and amount.

### 0b. Save path & duplication protection

**What one submit writes**

| Entry | Rows |
|---|---|
| Expense / income / transfer / card payment / reconcile | one `Ledger` row |
| New account / card | one `Accounts` row |
| Stock / MF purchase | `Ledger(stock_buy)` + `InvestmentLedger(buy)` + `Assets` upsert |
| Stock / MF sale | `Ledger(stock_sell)` + `InvestmentLedger(sell)` + `Assets` upsert |
| Physical asset purchase / sale | `Ledger` row + `InvestmentLedger(buy/sell, Book=physical)` + `Assets` insert/upsert |

All rows from one submit share a `WriteBatchID`. A trade row and its cash row
reference each other via `LinkedTradeID` / `LedgerEntryID`.

**Pipeline**

1. Generate `ClientRequestID` when the form renders.
2. Validate (amount, date, active account, category type, ≤ 8 tags, sanitize).
3. Duplicate check against the recent window (default 45 days).
4. Generate `txn_…` / `trd_…` / `ast_…` ULIDs and one `WriteBatchID`.
5. Write all rows in one Sheets `batch_update`, status `pending`.
6. Read back by ID, verify one row per ID and linked rows match, then set
   `posted`; invalidate caches.
7. Update `PaymentDefaults.LastUsedAccountID`, `Audit`, `NotificationLog`;
   `st.toast` success; generate a new `ClientRequestID`.

If a dependent write fails, the batch stays `pending` (excluded from balances)
and the UI offers **Retry finalize**. A reconciliation job finds rows by
`WriteBatchID` and completes or reverses them. Nothing is deleted.

**Duplicate rules**

| Entry | Warn when |
|---|---|
| Expense / income | same type + account, date ±2 days, amount exact or within 2%, description similarity ≥ 85 |
| Transfer / card payment | same from/to, date ±1 day, amount exact |
| Stock / MF trade | same asset + side, date ±1 day, quantity and price equal or within 1% |
| Recurring bill vs posted entry | same account/category, due date ±3 days, amount within 5% → offer "mark as paid" |

- **Hard block:** same `ClientRequestID` (double-click/retry) returns the
  existing entry.
- **Soft warning:** candidate panel with date, amount, account, description,
  tags. Actions: Cancel · View existing · Save anyway. Save anyway stores
  `DuplicateOfEntryID` and audits `duplicate_override` (optional reason).
- Reversed entries are ignored.
- New account/card and new asset also check normalized nickname/symbol; offer
  "add to existing holding" where relevant.
- Google Sheets cannot enforce uniqueness: re-read before append and verify
  after; a later Postgres adapter adds unique indexes on `ClientRequestID` and
  `IdempotencyKey`.

### 0c. Investment ledger separation

- The main `Ledger` records **cash**: `stock_buy` / `stock_sell` rows show money
  leaving/entering the brokerage or bank account.
- `InvestmentLedger` records the **trade**: asset, book (`investment` or
  `physical`), side, quantity, unit price, fees, gross/net amount, realized
  gain, and links back to the cash row.
- `Assets` is a rebuildable current-state cache (quantity, average cost, current
  value), not a second source of truth.
- `AssetPrices` stores a dated price series and `PortfolioSnapshots` stores
  derived values for funds-over-time charts, future portfolio balancing and
  exit analysis. Neither affects cash balances.
- Investment cash movements are **capital movements**, not expenses. They are
  excluded from expense and savings-rate KPIs but included in net worth
  (`cash + assets − liabilities`).
- Corrections use a reversal trade + reversal cash row, never an edit to
  quantity or average cost.

---

## 1. Expense

**Purpose:** money spent from an account or card.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Date | R | date | today | no future dates |
| Amount | R | number | — | > 0 |
| Paid from | R | dropdown of accounts/cards | last used | actual account: savings, current, wallet, cash, brokerage, or card. **For UPI, pick the linked savings/current account.** |
| Payment method | O | dropdown | inferred | UPI / netbanking / auto-debit / cheque / cash / card; inferred from the account (card → card, cash → cash, wallet → wallet). Becomes a `method` tag. |
| Description | O | text | — | free text; **drives tag + category suggestions** (see 1a) |
| Category | R | dropdown (Expenditure) | **suggested** | inline create; user can override |
| Tags | O | editable chips | **suggested** | add/remove before saving; max 8 |
| Private | O | checkbox | off | |

**Computed:** suggested tags (item / merchant / service / channel / method),
suggested category.
**Writes:** `Ledger(expense)` → `−Amount` on the chosen account; `TagIDs`
stored on the entry. If the account is a card, its outstanding increases; if
it is a bank/wallet/cash account, that balance decreases. Only one side
changes for an expense.
**UPI rule:** UPI is a payment-method tag on the bank account. The linked
savings/current balance is reduced directly — no separate "UPI account" is
involved.
**Default (v1):** a card expense shows a soft warning when it pushes
utilization above the threshold; it never blocks the entry.

---

## 1a. Description → tags & category extraction (Expense)

**Goal:** the user types one natural sentence; the app proposes tags and a
category; the user adds/removes chips; only then is the entry saved.

### Worked examples

| Description typed | Suggested tags (type) | Suggested category |
|---|---|---|
| "bought fruits from blinkit app" | `fruits` (item), `blinkit` (merchant), `online` (channel) | Groceries |
| "apples from swiggy" | `apples` + `fruits` (item), `swiggy` (merchant), `instamart` (service), `online` (channel) | Groceries |
| "butter, milk, bread from blinkit" | `butter`, `milk`, `bread` (item), `blinkit` (merchant), `online` | Groceries |
| "veggies from star market" | `veggies` (item), `star market` (merchant), `instore` (channel) | Groceries |
| "bhindi, potatoes from star market" | `bhindi`, `potatoes` (item), `veggies` (parent item), `star market` (merchant), `instore` | Groceries |

### Tag taxonomy

| Type | Examples | Purpose |
|---|---|---|
| `item` | fruits, apples, veggies, milk, bread, butter, chicken | what was bought |
| `merchant` | blinkit, swiggy, star market | where it was bought (store name is a tag) |
| `service` | instamart, dineout, food_delivery | which business of the merchant |
| `channel` | online, instore | where the purchase happened |
| `method` | upi, netbanking, auto-debit, cash, card | how the payment was made |
| `custom` | healthy, treat, office | user-defined |

- Canonical names are lowercase (`veggies`, not `Vegetable`).
- Each tag supports **aliases**: `vegetable`, `veg`, `sabzi` → `veggies`;
  `potato`, `potatoes`, `aloo` → `potatoes`; `blinkit app`, `instamart` →
  `blinkit`.
- Aliases are matched before display, so the ledger always stores the
  canonical tag.
- **Hierarchy:** a specific item automatically adds its parent tag.
  `apples` adds `fruits`; `bhindi` and `potatoes` add `veggies`. Both chips
  appear, and either can be removed before saving.
- **Merchant vs channel are independent:** `star market` adds the merchant tag
  `star market` and the channel tag `instore`; `blinkit` adds `blinkit` and
  `online`.

### Extraction pipeline (local, deterministic, no external API)

1. **Normalize**: lowercase, strip punctuation, singularize simple plurals,
   expand known aliases.
2. **Match**: scan 1–3 word n-grams against the tag/alias lexicon and learned
   rules; exact match > alias > contains > fuzzy (typos via `rapidfuzz`,
   optional dependency).
3. **Merchant & service resolution**: match merchant aliases, then resolve the
   service (explicit service keyword > grocery/item evidence > merchant
   default). Each service carries its own channel and category — see the
   Swiggy rules above.
   - online: `blinkit`, `swiggy`, `zepto`, `instamart`, `bigbasket`, `amazon`,
     `flipkart`, plus words `app`, `online`, `delivery`.
   - instore: `market`, `store`, `mall`, `shop`, `kirana`, plus an explicit
     store name not in the online list.
4. **Expand hierarchy**: add parent tags for matched items (`apples` →
   `fruits`; `bhindi`/`potatoes` → `veggies`).
5. **Item → category**: the item/parent tag set maps to a default category
   (fruits/veggies/milk/bread/butter → `Groceries`; prepared food → `Dining
   Out`; fuel → `Transport`; medicine → `Health`).
6. **Merchant → default category**: used only when no item evidence exists
   (e.g. `swiggy` alone → `Dining Out`; `swiggy` + `milk` → `Groceries`).
7. **Score and rank**: exact/alias 1.0, contains 0.9, fuzzy 0.7, learned
   0.8 + small boost for repeated use. Show suggestions above threshold.
8. **Return**: tag list, suggested category, merchant, channel, confidence,
   and a short reason per tag ("alias of vegetable", "parent of bhindi",
   "known online merchant").
9. **User edits**, then saves. Nothing is auto-saved without confirmation.

### Merchant services — Swiggy Instamart vs Swiggy Dineout

Swiggy is one merchant with multiple services. Resolve in this order:

1. **Explicit service keyword**:
   - `instamart`, `insta mart` → **Instamart** (online, Groceries)
   - `dineout`, `dine out`, `dining out`, `restaurant booking` → **Dineout**
     (instore, Dining Out)
   - `delivery`, `order food`, `dinner`, `lunch`, `breakfast` → **Food
     delivery** (online, Dining Out)
2. **Grocery item evidence** (`apples`, `milk`, `vegetables`…) → **Instamart**
   (online, Groceries), even without the word "instamart".
3. **Fallback** → **Food delivery** (online, Dining Out).

| Description typed | Tags | Category |
|---|---|---|
| "apples from swiggy" | `apples` + `fruits`, `swiggy`, `instamart`, `online` | Groceries |
| "milk from swiggy instamart" | `milk`, `swiggy`, `instamart`, `online` | Groceries |
| "dinner from swiggy" | `swiggy`, `food_delivery`, `online` | Dining Out |
| "swiggy dineout" | `swiggy`, `dineout`, `instore` | Dining Out |

### Conflict rule (general)

Merchant evidence sets the channel and a fallback category; **specific item
evidence wins over the merchant default**. `pizza from swiggy` → Dining Out;
`apples from swiggy` → Groceries. When confidence is low, leave the category
blank and let the user pick.

### UI behavior

- Description field lives **outside** a `st.form` (or has a "Suggest" button)
  so suggestions refresh on Enter/blur.
- Suggestions appear as pre-selected editable chips (`st.pills` or
  `st.multiselect` with `accept_new_options`).
- Each chip is removable; an "＋ Add tag" control creates a new tag.
- Category dropdown is pre-filled with the suggestion and shows a subtle
  "suggested from description" hint.
- Merchant and channel are **tags**, not separate fields.
- Suggested chips are grouped by type: **Items · Merchant · Channel · Custom**.
- Parent tags appear next to their specific item (`apples`, `fruits`).
- A "used before with this merchant" row offers quick-add chips.

### Learning loop

- On save, confirmed description → tags/category mappings are written to
  `TagRules` with `Source = learned`.
- Removing a suggested tag records negative feedback so it is not re-suggested
  for the same merchant/pattern.
- New manual tags create a learned rule; repeated use raises its priority.
- The lexicon is shared, but learned rules are scoped per user.

### Storage additions

**`Tags`**
| Column | Notes |
|---|---|
| TagID | `tag_001` |
| Name | canonical lowercase name |
| Type | item / merchant / service / channel / method / custom |
| Aliases | comma-separated |
| ParentTag | optional (`apples` → `fruits`) |
| DefaultCategoryID | optional (merchants/items) |
| IsActive | |

**`TagRules`**
| Column | Notes |
|---|---|
| RuleID | `rule_001` |
| Pattern | text or regex |
| MatchType | exact / contains / regex |
| OutputTagIDs | comma-separated |
| Channel | online / instore / blank |
| CategoryID | optional |
| Priority | integer (higher wins) |
| Source | seed / learned / manual |
| Hits | usage count |
| LastUsed | |
| IsActive | |

- `Ledger.Tags` stores **TagIDs** (comma-separated); the UI renders names.
- Optional `TagText` display column for readable Sheets export.

### Lexicon file

**`src/data/lexicon.yaml`** (created in this repo) is the growing word/tag list.
It is human-editable, version-controlled, and loaded locally at startup — no
network calls at runtime.

```yaml
version: 1
settings:
  max_tags_per_entry: 8
  auto_add_parent_tags: true
channels: { online: [...], instore: [...] }
services: { instamart: {...}, dineout: {...}, food_delivery: {...} }
items:    { apples: { parent: fruits, aliases: [...], category: Groceries } }
merchants: { swiggy: { default_service: food_delivery, category_services: {...} } }
units:    { kg: [...], g: [...], l: [...], ml: [...] }
```

- Adding a word or alias is a **data edit**, not a code change.
- Loaded by `src/data/lexicon.py`; validated against a small schema.
- Future: a **free LLM can propose additions offline** in batches; a human
  reviews and commits them to the YAML. It is never called at runtime.

### Tag analytics (month filter)

Because `Ledger.Tags` stores **TagIDs** alongside `Date`, we can answer:

| Question | Query |
|---|---|
| How much did I spend on Swiggy vs Blinkit this month? | merchant tag filter + sum `Amount` |
| How many times did I buy fruits? | `fruits` (parent rollup includes `apples`, `bananas`) + count |
| How many times did I have chicken? | `chicken` tag + count |
| Online vs instore split? | `channel` tag + sum |
| Which items do I buy most? | item tags ranked by count/amount |

- Default window = current month; switch to last 3 months, YTD, custom.
- Parent tags roll up children (`fruits` = `apples` + `bananas` + …).
- A tag can be compared across merchants (Swiggy Instamart vs Blinkit).
- Optional future: extract quantity/unit ("2 kg apples") and report totals.

### Implementation

- `src/services/tagging.py` — `suggest_tags(description, user, entry_type="expense") -> Suggestion`.
  The entry-type argument keeps income extraction available later without
  rework; v1 only calls it for expenses.
- `src/data/lexicon.yaml` — seed items, merchants, services, channels,
  aliases, category mappings.
- `src/data/lexicon.py` — load/validate the YAML.
- `src/ui/components/tag_editor.py` — chips, add/remove, suggestions.
- `tests/test_tagging.py` — the worked examples above plus typos, aliases,
  Swiggy service routing, and parent rollups.

### Decisions log (tagging)

| # | Decision | Status |
|---|---|---|
| 1 | Max 8 tags per entry | **Approved** |
| 2 | Auto-add parent tags (`apples` → `fruits`) | **Approved** |
| 3 | Seed Hindi/regional aliases (`bhindi`, `aloo`, `sabzi`) | **Approved** |
| 4 | Swiggy routing | **Approved with change:** Instamart = online + Groceries; Dineout = instore + Dining Out; fallback = food delivery (online, Dining Out) |
| 5 | Growing lexicon file | **Approved:** `src/data/lexicon.yaml`; future LLM additions are offline/reviewed only |
| 6 | Store tag IDs, filter by month | **Approved:** IDs in the ledger; analytics by month/merchant/item/parent rollup |
| 7 | Extraction on Income | **Deferred:** expenses only in v1; the engine keeps a per-entry-type switch so income can be enabled later without rework |

---

## 2. Income

**Purpose:** money received into an account.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Date | R | date | today | |
| Amount | R | number | — | **net amount actually credited** |
| Received in | R | dropdown of accounts | last used | |
| Income category | R | dropdown (Income) | last used | Salary, Interest, Dividend, Rent, Freelance, Gift/Refund, Other |
| Source / payer | O | text | — | nickname only ("TechCorp", "HDFC") |
| Description | O | text | — | sanitized |
| Tax withheld (TDS) | O | number | 0 | **information only**; not posted to the ledger. Future: tax assist fetches official tax data online and suggests tags/amounts. |
| Private | O | checkbox | off | |

**Computed:** gross = amount + TDS (display only, if TDS entered).
**Writes:** `Ledger(income)` → `+Amount`.

### 2a. Optional source-specific extras (only when category matches)
| Category | Extra optional fields |
|---|---|
| Salary | Employer nickname, pay component (monthly / bonus / reimbursement) |
| Interest | Bank nickname, FD reference nickname (not a number) |
| Dividend | Asset/company nickname |
| Rent | Property nickname (use the asset name) |
| Freelance | Client/project nickname |
| Gift / Refund | Short source note |

**Approved:** TDS is **information only** in v1 (not a tax expense). Future
**tax assist**: fetch official tax information online and suggest TDS/tax tags
on income entries. The user confirms every suggestion; no credentials stored.

### 2b. Future — tax assist (not v1)
- Pull tax-related data from an authorized source (e.g. annual tax statement)
  and propose `tds`, `tax_paid`, `tax_refund` tags and amounts.
- Applied as suggestions on income entries, never auto-posted.
- Requires explicit consent and a secure, read-only integration.

---

## 3. Transfer

**Purpose:** move money between your own accounts, or pay a credit card.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Date | R | date | today | |
| From account | R | dropdown | default/last used | prefilled from `PaymentDefaults`; confirm before submit |
| To account | R | dropdown | — | must differ from "from" |
| Amount | R | number | — | > 0 |
| Note | O | text | — | |
| Private | O | checkbox | off | |

**Computed:** nothing.
**Writes:** `Ledger(transfer)` → `−Amount` from "from", `+Amount` to "to".
**Excluded from income/expense/savings KPIs.**

**Approved:** card bill payments use the **dedicated Card payment form**
(section 9); a card can still appear as the "to" side of an advanced transfer.

---

## 4. New credit card

**Purpose:** register a card you received. No card number is ever collected.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Nickname | R | text | — | "HDFC Regalia" — sanitizer rejects number-like text |
| Issuer / bank | O | text | — | "HDFC" (bank name only) |
| Credit limit | R | number | — | > 0 |
| Statement day | O | 1–31 | 1 | day of month |
| Due day | R | 1–31 | 10 | warn if equal to statement day |
| Opening outstanding | O | number | 0 | amount already owed when added |
| Opening date | R | date | today | |
| Currency | O | dropdown | INR | |
| Notes | O | text | — | sanitized |

**Writes:** `Accounts(kind=credit_card)`.
**Computed:** available limit = limit − current outstanding.
**Approved:** statement day is **optional**; if set, statement-day alerts fire,
otherwise they are skipped and due-day alerts still work.

---

## 5. New account

**Purpose:** register a bank / UPI / wallet / cash / brokerage / loan account.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Nickname | R | text | — | "Salary Account", "Primary UPI" |
| Kind | R | dropdown | savings | savings / current / wallet / cash / brokerage / loan (`upi` is a payment method, not a kind) |
| Issuer / provider | O | text | — | "SBI", "GooglePay" |
| Currency | O | dropdown | INR | |
| Opening balance | R | number | 0 | for **loan**, label becomes "Outstanding" and is stored as a liability |
| Opening date | R | date | today | |
| Notes | O | text | — | sanitized |

**Writes:** `Accounts(...)`.
**Computed:** current balance = opening balance + ledger postings.
**Approved:** for loans the user enters the outstanding as a **positive
number**; the app negates it internally (`balance = −outstanding`) and displays
the positive outstanding. A payment is a transfer into the loan account.

---

## 6. Stock / mutual fund purchase

**Purpose:** buy a financial asset; cash leaves an account and the holding grows.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Date | R | date | today | |
| Paid from | R | dropdown (cash/brokerage/savings) | default/last used | prefilled from `PaymentDefaults`; confirm |
| Asset type | R | dropdown | equity | equity / mutual_fund / bond / fd / crypto / other |
| Existing holding? | O | dropdown | new | choose to add to a holding |
| Asset name | R | text | — | "NIFTY 50 ETF" |
| Symbol | O | text | — | "NIFTYBEES" |
| Quantity | R | number | — | > 0 |
| Unit price | R | number | — | > 0 |
| Fees / charges | O | number | 0 | capitalized into cost basis; stored on the entry |
| Notes | O | text | — | |
| Private | O | checkbox | off | applied to the ledger entry |

**Computed:** total cost = (quantity × price) + fees; new weighted average cost
per unit (fees included).
**Writes:** `Ledger(stock_buy)` → `−total cost` (cash movement, with
`LinkedTradeID`); `InvestmentLedger(buy)` → trade row with quantity, unit price,
fees, net amount, `LedgerEntryID`; upsert `Assets` (quantity += bought, weighted
average cost updated, `LastRebuiltAt`).

**Approved:** fees are **capitalized** into cost basis. No separate fee
breakdown entry in v1, but the fee amount is stored on the purchase entry so a
breakdown can be added later without losing data.

---

## 7. Asset purchase (house, gold, vehicle, etc.)

**Purpose:** buy a non-trading asset you will track in the register.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Date | R | date | today | |
| Asset type | R | dropdown | real_estate | real_estate / gold / vehicle / other |
| Asset name | R | text | — | "Flat 302", "Gold 50g" |
| Quantity | R | number | 1 | units bought; 1 for property, grams for gold |
| Unit | O | text | unit | grams, sqft, units, etc. |
| Paid from | R | dropdown | default/last used | prefilled from `PaymentDefaults`; confirm |
| Purchase price | R | number | — | total price, > 0 |
| Fees / registration | O | number | 0 | capitalized into cost basis |
| Current estimated value | O | number | acquisition cost | |
| Valuation date | O | date | today | |
| Notes | O | text | — | sanitized |

**Computed:** acquisition cost = purchase price + fees; cost per unit =
acquisition cost ÷ quantity.
**Writes:** `Ledger(asset_purchase)` → `−acquisition cost` (cash row);
`InvestmentLedger(buy, Book=physical)` → trade row with quantity, unit price,
fees, net amount; create `Assets` with quantity, unit, average cost per unit and
current value.

**Approved:** physical asset purchases use the new **`asset_purchase`** ledger
type (separate from `stock_buy`). Fees are **capitalized** and stored on the
entry; no separate fee breakdown in v1.

---

## 8. Asset sales (two separate flows)

Stock sales and physical asset sales are **different flows and ledger types**.
Both support partial sales.

### 8.1 Stock / mutual fund sale

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Date | R | date | today | |
| Holding | R | dropdown of active financial assets | — | equity / MF / bond / crypto |
| Quantity sold | R | number | full holding | ≤ quantity held |
| Sale price per unit | O | number | — | prefill total if entered |
| Total proceeds | R | number | — | net amount agreed, > 0 |
| Fees / commission | O | number | 0 | deducted from proceeds |
| Received in | R | dropdown | default/last used | prefilled; confirm |
| Notes | O | text | — | |
| Private | O | checkbox | off | |

**Computed:** cost basis = avg cost × quantity sold; net proceeds = proceeds −
fees; realized gain = net proceeds − cost basis.
**Writes:** `Ledger(stock_sell)` → `+net proceeds` (cash movement, with
`LinkedTradeID`); `InvestmentLedger(sell)` → trade row with quantity, unit
price, fees, net amount, realized gain, `LedgerEntryID`; reduce the holding;
mark disposed when quantity reaches zero.
**Approved:** partial stock sales supported; separate from physical assets.
The main `Ledger` records only the cash side; `InvestmentLedger` is the trade
history used for charts, allocation and future exit analysis.

### 8.2 Physical asset sale (house, gold, vehicle)

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Date | R | date | today | |
| Asset | R | dropdown of active physical assets | — | real_estate / gold / vehicle / other |
| Quantity sold | R | number | full holding | ≤ quantity held; property is usually 1 |
| Sale proceeds | R | number | — | total received, > 0 |
| Fees / commission | O | number | 0 | deducted from proceeds |
| Received in | R | dropdown | default/last used | prefilled; confirm |
| Notes | O | text | — | |
| Private | O | checkbox | off | |

**Computed:** cost basis = avg cost × quantity sold; net proceeds = proceeds −
fees; realized gain = net proceeds − cost basis.
**Writes:** `Ledger(asset_sale)` → `+net proceeds` (cash row);
`InvestmentLedger(sell, Book=physical)` → trade row with quantity, unit price,
fees, net amount, realized gain; reduce or dispose the asset.
**Approved:** partial sales are supported for all assets; stock and physical
asset sales remain separate flows (`stock_sell` vs `asset_sale`).

---

## 9. Card payment

**Purpose:** pay a credit card bill from an account.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Date | R | date | today | |
| Pay from | R | dropdown of bank/wallet/cash accounts | default/last used | prefilled from `PaymentDefaults` (`bill_payment`); confirm before submit |
| Card | R | dropdown of cards | — | |
| Amount | R | number | current outstanding | editable, may be partial |
| Payment method | O | dropdown | netbanking | UPI / netbanking / auto-debit / cheque; becomes a `method` tag |
| Note | O | text | — | |

**Computed:** remaining outstanding = outstanding − amount; source balance after
= source − amount.
**Writes:** `Ledger(transfer)` → `−Amount` from the source account, `+Amount`
to the card. Both balances update from the same row.
**Example:** savings ₹1,000, card outstanding ₹500, pay ₹200 → savings ₹800,
card outstanding ₹300.
**Approved:** dedicated Card payment form (it is a transfer underneath); the
source account is prefilled but always confirmed.

---

## 10. Reconcile / balance adjustment

**Purpose:** correct the app's balance to match reality (bank charges, missed
entries).

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Date | R | date | today | |
| Account | R | dropdown | — | |
| Actual balance now | R | number | current computed balance | |
| Reason | R | dropdown | — | bank charge / interest / missed entry / correction |
| Note | O | text | — | sanitized |
| Confirm | R | checkbox | — | required before posting |

**Computed:** difference = actual − computed.
**Writes:** `Ledger(adjustment)` for the difference; `Audit` row.
**Approved:** manual reconciliation is allowed with a **required reason** and
a confirmation checkbox. The adjustment is written to the ledger and audit
log; nothing is overwritten.

---

## 11. Set spending limit / budget

**Purpose:** personalized caps and warnings.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Scope | R | dropdown | overall | overall / category / account (card) |
| Target | R (if scope ≠ overall) | dropdown | — | category or account |
| Period | R | dropdown | monthly recurring | monthly recurring / specific month |
| Amount | R | number | — | > 0 |
| Warn at | O | % | 80 | warning threshold |
| Active | O | toggle | on | |

**Writes:** `Limits(...)`. No ledger entry.
**Dashboard:** progress bar, remaining amount, warnings at "warn at %" and 100%.

---

## 12. Recurring bill / reminder *(included in v1)*

**Purpose:** upcoming fixed payments; reminder only, no auto-posting in v1.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Name | R | text | — | "Internet", "Rent" |
| Amount | R | number | — | > 0 |
| Account / card | R | dropdown | default/last used | prefilled from `PaymentDefaults`; confirm |
| Category | R | dropdown | — | |
| Frequency | R | dropdown | monthly | weekly / monthly / quarterly / yearly |
| Next due date | R | date | — | may be future |
| Remind me (days before) | O | number | 7 | |
| Notify me via | O | dropdown | in-app | in-app / email / both |
| Auto-post | O | toggle | off | keep off in v1 |
| Active | O | toggle | on | |

**Writes:** `RecurringRules(...)`; dashboard "Upcoming bills" + alerts.
**Approved:** recurring bills are **included in v1** (reminder only; no
auto-posting).

### 12a. Daily notifications / pending items

A daily check runs on app load and, optionally, as an email digest.

| Trigger | Alert |
|---|---|
| Card due day approaching | "HDFC Regalia due in N days" |
| Card statement day (optional) | "Statement generated — review pending entries" |
| Recurring bill due | "Internet bill due in N days" |
| Pending ledger entries older than N days | "3 entries still pending" |
| Budget threshold crossed | "Groceries at 85% of budget" |
| Low available limit | "Card available limit below ₹X" |
| Reconcile age | "Savings not reconciled for 30 days" |

- **In-app:** computed on page load; shown as banners + a "Pending items"
  panel. No background process needed.
- **Email (optional):** a Google Apps Script time-driven trigger (free, runs
  daily, reads the Sheet) or a GitHub Actions cron job sends one digest.
  Requires opt-in and an email address in `Settings`.
- `NotificationLog` stores `Timestamp`, `User`, `Type`, `RecordID`, `Channel`,
  `Status` to avoid duplicate sends.
- Statement day is optional: if blank, statement alerts are skipped; due-day
  alerts still work.

---

## 13. Edit / reverse an entry *(operation, not a form)*

**Purpose:** correct a past mistake without deleting history.

| Field | R/O | Input | Default | Notes |
|---|---|---|---|---|
| Entry | R | pick from recent/ledger | — | |
| Reason | R | text | — | required |
| Action | R | radio | reverse | reverse / reverse & re-enter |
| Reversal date | R | date | today | |

**Writes:** a mirrored reversal entry + link in `LinkedEntryID`; `Audit` row.
**Approved:** "reverse & re-enter" opens the matching entry form pre-filled;
the reversal is always posted first, then the corrected entry.

---

## Summary table

| # | Entry type | Required fields (short) | Ledger effect |
|---|---|---|---|
| 1 | Expense | date, amount, account, description → suggested category/tags | − account |
| 2 | Income | date, amount, account, category | + account |
| 3 | Transfer | date, from, to, amount | − from, + to |
| 4 | New credit card | nickname, limit, due day | none (sets up account) |
| 5 | New account | nickname, kind, opening balance, date | none (sets up account) |
| 6 | Stock/MF purchase | date, account, asset, qty, price, fees | − account `stock_buy` + `InvestmentLedger(buy)`, asset grows |
| 7 | Asset purchase | date, type, name, qty, price, account | − account `asset_purchase` + `InvestmentLedger(buy, physical)`, asset created |
| 8a | Stock/MF sale | date, holding, qty sold, proceeds, account | + account `stock_sell` + `InvestmentLedger(sell)`, asset shrinks |
| 8b | Physical asset sale | date, asset, qty sold, proceeds, account | + account `asset_sale` + `InvestmentLedger(sell, physical)`, asset shrinks |
| 9 | Card payment | date, from, card, amount | − bank, + card |
| 10 | Reconcile | date, account, actual balance, reason | adjustment |
| 11 | Set limit | scope, period, amount | none |
| 12 | Recurring bill (v1) | name, amount, account, category, frequency, notify | none (reminder + daily alerts) |
| 13 | Reverse entry | entry, reason | mirror entry |

---

## Decisions log (locked)

| # | Decision | Status |
|---|---|---|
| 1 | TDS handling | **Approved:** information only in v1; future online tax assist suggests TDS/tax tags on income |
| 2 | Fees on purchases | **Approved:** capitalize into cost basis; no breakdown entry in v1, but the fee is stored on the entry for later |
| 3 | Physical asset purchases | **Approved:** new `asset_purchase` ledger type |
| 4 | Partial asset sales | **Approved:** supported for all assets; stock sales (`stock_sell`) and physical asset sales (`asset_sale`) are separate flows |
| 5 | Card payment | **Approved:** dedicated form (transfer underneath) |
| 6 | Statement day | **Approved:** optional; daily notifications for pending items, due dates and statements |
| 7 | Loans | **Approved:** user enters positive outstanding; app stores/display it as a liability |
| 8 | Reconcile | **Approved:** manual adjustments allowed with a required reason and confirmation |
| 9 | Recurring bills | **Approved with change:** included in v1, reminder only (no auto-posting) |
| 10 | Future dates | **Approved:** blocked for ledger entries; allowed for bills/reminders |
| 11 | Default accounts per method | **Approved:** prefill UPI/card/bill sources; user always confirms |
| 12 | Confirmation summary | **Approved:** every entry shows a final Confirm/Cancel summary |
| 13 | Tag limit | **Approved:** max 8 |
| 14 | Parent tags | **Approved:** auto-add `fruits` with `apples`, `veggies` with `bhindi` |
| 15 | Hindi/regional aliases | **Approved** |
| 16 | Swiggy routing | **Approved:** Instamart = online + Groceries; Dineout = instore + Dining Out; fallback = food delivery |
| 17 | Lexicon file | **Approved:** `src/data/lexicon.yaml`; future LLM additions are offline/reviewed only |
| 18 | Tag IDs + month analytics | **Approved:** tag IDs in the ledger; count/amount by merchant/item/parent/period |
| 19 | Income extraction | **Deferred:** expenses only in v1; per-entry-type switch available later |
| 20 | Tax assist | **Future:** online tax data fetch + suggestions; not v1 |

---

## Appendix A — Balance mechanics (worked examples)

### Setup
- Savings account `acc_sav`: opening balance **₹1,000**.
- Credit card `card_hdfc`: opening outstanding **₹0** (stored internally as a
  liability).
- Optional stored-value wallet `acc_wallet`: opening **₹0**.

### A. Groceries ₹200 paid by UPI from savings
Entry: `expense`, account `acc_sav`, amount ₹200, method tag `upi`.

| Account | Calculation | Balance |
|---|---|---|
| Savings | 1,000 − 200 | **₹800** |
| Card | 0 | ₹0 |

UPI is a **method tag**, not an account. The savings balance is reduced
directly. There is no "UPI account" to update.

### B. Groceries ₹200 paid by credit card
Entry: `expense`, account `card_hdfc`, amount ₹200, method tag `card`.

| Account | Calculation | Balance |
|---|---|---|
| Savings | unchanged | ₹1,000 |
| Card outstanding | 0 + 200 | **₹200** |

### C. Pay ₹200 card bill from savings
Entry: `transfer`, from `acc_sav`, to `card_hdfc`, amount ₹200.

| Account | Calculation | Balance |
|---|---|---|
| Savings | 1,000 − 200 | **₹800** |
| Card outstanding | 200 − 200 | **₹0** |

One `transfer` row updates both sides. The app does not guess the source
account — you select "Pay from" once, and both balances are derived from that
row.

### D. Optional stored-value wallet (PhonePe/Amazon Pay balance)
Only create a `wallet` account if it holds its own money.

| Step | Entry | Savings | Wallet |
|---|---|---|---|
| Top up ₹500 | transfer savings → wallet | ₹500 | ₹500 |
| UPI purchase ₹200 | expense from wallet | ₹500 | **₹300** |

If your UPI is linked directly to savings, use example **A** instead; do not
create a wallet account.

### E. Balance formula

```text
balance(account, as_of) =
    opening_balance
  + Σ signed postings up to as_of
```

Signs: income/interest/dividend/`stock_sell`/`asset_sale` → `+`;
expense/fee/`stock_buy`/`asset_purchase` → `−`; transfer → `−` from, `+` to;
adjustment → explicit.

Liability accounts (cards, loans) store the opening outstanding as a negative
number and display `outstanding = −balance`. A card purchase makes the balance
more negative (outstanding up); a card payment makes it less negative
(outstanding down).
