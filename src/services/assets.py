"""Investment and physical-asset register.

``InvestmentLedger`` is the trade history. ``Assets`` is a rebuildable cache of
the current holding, never a second source of truth. Cash movement is written to
the main ``Ledger`` at the same time.
"""

from __future__ import annotations

from datetime import date

from src.db.repo import append_rows, read_tab, update_row
from src.services.ledger import commit_batch, new_ledger_row
from src.utils.ids import as_int, clean_text, new_id, now_iso
from src.utils.privacy import sanitize_free_text

FINANCIAL_TYPES = ["equity", "mutual_fund", "bond", "fd", "crypto"]
PHYSICAL_TYPES = ["real_estate", "gold", "vehicle", "other"]
ALL_ASSET_TYPES = [*FINANCIAL_TYPES, *PHYSICAL_TYPES]

ASSET_TYPE_LABELS = {
    "equity": "Equity",
    "mutual_fund": "Mutual fund",
    "bond": "Bond",
    "fd": "Fixed deposit",
    "crypto": "Crypto",
    "real_estate": "Real estate",
    "gold": "Gold",
    "vehicle": "Vehicle",
    "other": "Other",
}

IGNORED_STATUSES = {"pending", "void", "cancelled", "failed"}


def book_for(asset_type: str) -> str:
    return "physical" if str(asset_type).strip().lower() in PHYSICAL_TYPES else "investment"


def _asset_rows(user: str | None = None) -> list[dict]:
    df = read_tab("Assets")
    if df.empty:
        return []
    rows = df.to_dict("records")
    if user is not None:
        rows = [r for r in rows if str(r.get("User", "")).strip() == user]
    return rows


def list_assets(user: str, book: str | None = None, active_only: bool = True) -> list[dict]:
    rows = _asset_rows(user)
    if active_only:
        rows = [
            r
            for r in rows
            if str(r.get("IsActive", "TRUE")).strip().lower()
            not in {"false", "0", "no", "off"}
        ]
    if book == "investment":
        rows = [
            r
            for r in rows
            if str(r.get("AssetType", "")).strip().lower() in FINANCIAL_TYPES
        ]
    elif book == "physical":
        rows = [
            r
            for r in rows
            if str(r.get("AssetType", "")).strip().lower() in PHYSICAL_TYPES
        ]
    rows.sort(key=lambda r: (str(r.get("AssetType", "")), str(r.get("Name", "")).lower()))
    return rows


def get_asset(asset_id_value: str, user: str | None = None) -> dict | None:
    for row in _asset_rows(user):
        if str(row.get("AssetID", "")).strip() == str(asset_id_value).strip():
            return row
    return None


def find_asset(
    user: str,
    name: str,
    symbol: str = "",
    asset_type: str = "",
    account_id: str = "",
) -> dict | None:
    target_name = clean_text(name).lower()
    target_symbol = clean_text(symbol).lower()
    for row in list_assets(user, active_only=True):
        if asset_type and str(row.get("AssetType", "")).strip().lower() != asset_type.strip().lower():
            continue
        if account_id and str(row.get("AccountID", "")).strip() != account_id.strip():
            continue
        row_name = str(row.get("Name", "")).strip().lower()
        row_symbol = str(row.get("Symbol", "")).strip().lower()
        if target_symbol and row_symbol and target_symbol == row_symbol:
            return row
        if target_name and row_name == target_name:
            return row
    return None


def asset_label(row: dict) -> str:
    name = str(row.get("Name", "")).strip() or "Unnamed"
    symbol = str(row.get("Symbol", "")).strip()
    asset_type = ASSET_TYPE_LABELS.get(
        str(row.get("AssetType", "")).strip().lower(), str(row.get("AssetType", ""))
    )
    suffix = f" ({symbol})" if symbol else ""
    return f"{name}{suffix} · {asset_type}"


def asset_options(
    user: str, book: str | None = None, active_only: bool = True
) -> tuple[list[str], dict[str, str]]:
    labels = {
        asset_label(row): str(row.get("AssetID"))
        for row in list_assets(user, book=book, active_only=active_only)
    }
    return list(labels.keys()), labels


def _new_asset_row(
    user: str,
    asset_type: str,
    name: str,
    symbol: str,
    account_id: str,
    quantity: float,
    avg_cost: int,
    current_price: int,
    unit: str,
) -> dict:
    return {
        "AssetID": new_id("ast"),
        "Timestamp": now_iso(),
        "User": user,
        "AccountID": account_id,
        "Name": sanitize_free_text(name, 80),
        "AssetType": asset_type,
        "Symbol": clean_text(symbol, 30).upper(),
        "Quantity": round(quantity, 6),
        "Unit": clean_text(unit, 12) or ("units" if book_for(asset_type) == "investment" else "unit"),
        "AvgCost": int(avg_cost),
        "CurrentPrice": int(current_price),
        "CurrentValue": int(round(quantity * current_price)),
        "ValuationDate": date.today().isoformat(),
        "IsActive": "TRUE",
        "LastRebuiltAt": now_iso(),
        "DisposedDate": "",
        "SaleProceeds": 0,
        "RealizedGain": 0,
    }


def _save_asset(asset: dict, is_new: bool) -> None:
    if is_new:
        append_rows("Assets", [asset])
    else:
        update_row("Assets", "AssetID", str(asset.get("AssetID")), asset)


def record_buy(
    user: str,
    entry_date: date | str,
    account_id: str,
    asset_type: str,
    name: str,
    quantity: float,
    unit_price_paise: int,
    fees_paise: int = 0,
    symbol: str = "",
    unit: str = "",
    notes: str = "",
    is_private: bool = False,
    client_request_id: str = "",
    existing_asset_id: str = "",
    duplicate_of_entry_id: str = "",
) -> dict:
    asset_type = str(asset_type or "").strip().lower()
    if asset_type not in ALL_ASSET_TYPES:
        raise ValueError("Choose an asset type.")
    if not clean_text(name):
        raise ValueError("Asset name is required.")
    quantity = float(quantity or 0)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    unit_price = int(unit_price_paise or 0)
    if unit_price <= 0:
        raise ValueError("Unit price must be greater than zero.")
    fees = max(0, int(fees_paise or 0))
    gross = int(round(quantity * unit_price))
    total_cash = gross + fees

    existing = get_asset(existing_asset_id, user) if existing_asset_id else None
    if existing is None:
        existing = find_asset(user, name, symbol, asset_type, account_id)

    if existing:
        old_qty = float(existing.get("Quantity") or 0)
        old_cost = old_qty * as_int(existing.get("AvgCost"))
        new_qty = old_qty + quantity
        new_cost = old_cost + gross + fees
        avg_cost = int(round(new_cost / new_qty)) if new_qty else unit_price
        asset = dict(existing)
        asset.update(
            {
                "AccountID": account_id,
                "Name": sanitize_free_text(name or asset.get("Name"), 80),
                "Symbol": clean_text(symbol or asset.get("Symbol"), 30).upper(),
                "Quantity": round(new_qty, 6),
                "AvgCost": avg_cost,
                "CurrentPrice": unit_price,
                "CurrentValue": int(round(new_qty * unit_price)),
                "ValuationDate": str(entry_date),
                "IsActive": "TRUE",
                "LastRebuiltAt": now_iso(),
                "DisposedDate": "",
            }
        )
        is_new = False
    else:
        avg_cost = int(round((gross + fees) / quantity)) if quantity else unit_price
        asset = _new_asset_row(
            user, asset_type, name, symbol, account_id, quantity, avg_cost, unit_price, unit
        )
        is_new = True

    trade_id = new_id("trd")
    ledger_type = "stock_buy" if book_for(asset_type) == "investment" else "asset_purchase"
    ledger_row = new_ledger_row(
        user=user,
        entry_type=ledger_type,
        entry_date=entry_date,
        amount_paise=total_cash,
        account_id=account_id,
        fees_paise=fees,
        category_id="",
        description=notes or f"Buy {name}",
        is_private=is_private,
        client_request_id=client_request_id,
        linked_trade_id=trade_id,
        duplicate_of_entry_id=duplicate_of_entry_id,
    )
    trade_row = {
        "TradeID": trade_id,
        "WriteBatchID": "",
        "Timestamp": now_iso(),
        "Date": str(entry_date),
        "User": user,
        "AssetID": str(asset["AssetID"]),
        "Book": book_for(asset_type),
        "Side": "buy",
        "Quantity": round(quantity, 6),
        "UnitPrice": unit_price,
        "Fees": fees,
        "GrossAmount": gross,
        "NetAmount": total_cash,
        "AccountID": account_id,
        "LedgerEntryID": ledger_row["EntryID"],
        "RealizedGain": 0,
        "Notes": sanitize_free_text(notes, 200),
        "Status": "pending",
        "ReversalOfTradeID": "",
    }
    result = commit_batch(
        user,
        [ledger_row],
        [trade_row],
        audit_action="buy_asset",
        audit_meta={"asset_id": asset["AssetID"], "book": book_for(asset_type)},
        default_method="netbanking",
        source_account_id=account_id,
    )
    result["asset_id"] = asset["AssetID"]
    try:
        _save_asset(asset, is_new)
    except Exception as exc:
        result["asset_warning"] = f"Trade saved; holdings cache will need a rebuild: {exc}"
    return result


def record_sell(
    user: str,
    entry_date: date | str,
    asset_id: str,
    quantity: float,
    total_proceeds_paise: int,
    account_id: str,
    fees_paise: int = 0,
    unit_price_paise: int = 0,
    notes: str = "",
    is_private: bool = False,
    client_request_id: str = "",
    duplicate_of_entry_id: str = "",
) -> dict:
    asset = get_asset(asset_id, user)
    if not asset:
        raise ValueError("Holding not found.")
    held = float(asset.get("Quantity") or 0)
    quantity = float(quantity or 0)
    if quantity <= 0:
        raise ValueError("Quantity sold must be greater than zero.")
    if quantity > held + 1e-6:
        raise ValueError(f"Only {held:g} units are held.")
    proceeds = int(total_proceeds_paise or 0)
    if proceeds <= 0:
        raise ValueError("Sale proceeds must be greater than zero.")
    fees = max(0, int(fees_paise or 0))
    net = max(0, proceeds - fees)
    unit_price = int(unit_price_paise or 0) or int(round(proceeds / quantity))
    avg_cost = as_int(asset.get("AvgCost"))
    cost_basis = int(round(avg_cost * quantity))
    realized = net - cost_basis
    asset_type = str(asset.get("AssetType", "")).strip().lower()
    book = book_for(asset_type)

    trade_id = new_id("trd")
    ledger_type = "stock_sell" if book == "investment" else "asset_sale"
    ledger_row = new_ledger_row(
        user=user,
        entry_type=ledger_type,
        entry_date=entry_date,
        amount_paise=net,
        account_id=account_id,
        fees_paise=fees,
        description=notes or f"Sell {asset.get('Name', '')}",
        is_private=is_private,
        client_request_id=client_request_id,
        linked_trade_id=trade_id,
        duplicate_of_entry_id=duplicate_of_entry_id,
    )
    trade_row = {
        "TradeID": trade_id,
        "WriteBatchID": "",
        "Timestamp": now_iso(),
        "Date": str(entry_date),
        "User": user,
        "AssetID": asset_id,
        "Book": book,
        "Side": "sell",
        "Quantity": round(quantity, 6),
        "UnitPrice": unit_price,
        "Fees": fees,
        "GrossAmount": proceeds,
        "NetAmount": net,
        "AccountID": account_id,
        "LedgerEntryID": ledger_row["EntryID"],
        "RealizedGain": realized,
        "Notes": sanitize_free_text(notes, 200),
        "Status": "pending",
        "ReversalOfTradeID": "",
    }
    result = commit_batch(
        user,
        [ledger_row],
        [trade_row],
        audit_action="sell_asset",
        audit_meta={"asset_id": asset_id, "quantity": quantity, "realized_gain": realized},
        default_method="netbanking",
        source_account_id=account_id,
    )
    result["asset_id"] = asset_id
    result["realized_gain"] = realized

    new_qty = max(0.0, held - quantity)
    updated = dict(asset)
    updated["Quantity"] = round(new_qty, 6)
    updated["CurrentValue"] = int(round(new_qty * as_int(asset.get("CurrentPrice"))))
    updated["LastRebuiltAt"] = now_iso()
    updated["SaleProceeds"] = as_int(asset.get("SaleProceeds")) + net
    updated["RealizedGain"] = as_int(asset.get("RealizedGain")) + realized
    if new_qty <= 1e-9:
        updated["IsActive"] = "FALSE"
        updated["DisposedDate"] = str(entry_date)
        updated["Quantity"] = 0
        updated["CurrentValue"] = 0
    try:
        _save_asset(updated, False)
    except Exception as exc:
        result["asset_warning"] = f"Trade saved; holdings cache will need a rebuild: {exc}"
    return result


def update_valuation(
    user: str,
    asset_id: str,
    price_paise: int,
    valuation_date: date | str | None = None,
) -> dict:
    asset = get_asset(asset_id, user)
    if not asset:
        raise ValueError("Holding not found.")
    price = int(price_paise or 0)
    if price < 0:
        raise ValueError("Price cannot be negative.")
    when = str(valuation_date or date.today())
    quantity = float(asset.get("Quantity") or 0)
    updated = dict(asset)
    updated["CurrentPrice"] = price
    updated["CurrentValue"] = int(round(quantity * price))
    updated["ValuationDate"] = when
    updated["LastRebuiltAt"] = now_iso()
    update_row("Assets", "AssetID", asset_id, updated)
    append_rows(
        "AssetPrices",
        [
            {
                "AssetID": asset_id,
                "Date": when,
                "PricePerUnit": price,
                "Source": "manual",
                "UpdatedAt": now_iso(),
            }
        ],
    )
    return updated


def rebuild_assets(user: str) -> dict:
    """Recompute quantity, average cost and realized gain from posted trades."""
    assets = {str(row.get("AssetID")): dict(row) for row in _asset_rows(user)}
    df = read_tab("InvestmentLedger")
    trades = [] if df.empty else df.to_dict("records")
    trades = [
        row
        for row in trades
        if str(row.get("User", "")).strip() == user
        and str(row.get("Status", "")).strip().lower() not in IGNORED_STATUSES
    ]
    trades.sort(key=lambda r: (str(r.get("Date", "")), str(r.get("Timestamp", ""))))

    state: dict[str, dict] = {}
    for trade in trades:
        asset_id = str(trade.get("AssetID", "")).strip()
        if not asset_id:
            continue
        current = state.setdefault(
            asset_id,
            {"quantity": 0.0, "cost": 0.0, "realized": 0, "proceeds": 0, "last_price": 0, "last_date": ""},
        )
        qty = float(trade.get("Quantity") or 0)
        side = str(trade.get("Side", "")).strip().lower()
        gross = as_int(trade.get("GrossAmount"))
        fees = as_int(trade.get("Fees"))
        net = as_int(trade.get("NetAmount"))
        if side == "buy":
            current["quantity"] += qty
            current["cost"] += gross + fees
            current["last_price"] = as_int(trade.get("UnitPrice"))
        else:
            avg = current["cost"] / current["quantity"] if current["quantity"] else 0
            current["quantity"] = max(0.0, current["quantity"] - qty)
            current["cost"] = max(0.0, current["cost"] - avg * qty)
            current["realized"] += net - int(round(avg * qty))
            current["proceeds"] += net
            current["last_price"] = as_int(trade.get("UnitPrice"))
        current["last_date"] = str(trade.get("Date", ""))

    rebuilt = 0
    for asset_id, asset in assets.items():
        current = state.get(asset_id)
        if not current:
            continue
        qty = current["quantity"]
        avg_cost = int(round(current["cost"] / qty)) if qty else as_int(asset.get("AvgCost"))
        price = as_int(asset.get("CurrentPrice")) or current["last_price"]
        asset.update(
            {
                "Quantity": round(qty, 6),
                "AvgCost": avg_cost,
                "CurrentPrice": price,
                "CurrentValue": int(round(qty * price)),
                "RealizedGain": current["realized"],
                "SaleProceeds": current["proceeds"],
                "LastRebuiltAt": now_iso(),
            }
        )
        if qty <= 1e-9:
            asset["IsActive"] = "FALSE"
            asset["Quantity"] = 0
            asset["CurrentValue"] = 0
            asset["DisposedDate"] = asset.get("DisposedDate") or current["last_date"]
        else:
            asset["IsActive"] = "TRUE"
            asset["DisposedDate"] = ""
        try:
            update_row("Assets", "AssetID", asset_id, asset)
            rebuilt += 1
        except Exception:
            continue
    return {"assets": rebuilt, "trades": len(trades)}


def portfolio_value(user: str) -> int:
    return sum(as_int(row.get("CurrentValue")) for row in list_assets(user, active_only=True))
