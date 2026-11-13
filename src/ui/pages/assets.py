"""Holdings, manual valuations and the investment trade history."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.db.repo import read_tab
from src.services.assets import (
    ASSET_TYPE_LABELS,
    asset_label,
    get_asset,
    list_assets,
    rebuild_assets,
    update_valuation,
)
from src.services.ledger import compute_balances
from src.ui.components import empty_state, esc, money, page_header, stats_grid
from src.ui.pages.entry import queue_plan
from src.utils.ids import as_int
from src.utils.money import from_paise, to_paise


def _holding_totals(rows: list[dict]) -> dict:
    value = sum(as_int(row.get("CurrentValue")) for row in rows)
    cost = sum(
        int(round(float(row.get("Quantity") or 0) * as_int(row.get("AvgCost"))))
        for row in rows
    )
    realized = sum(as_int(row.get("RealizedGain")) for row in rows)
    return {"value": value, "cost": cost, "unrealized": value - cost, "realized": realized}


def _holding_block(asset: dict, user: str, key_prefix: str) -> None:
    asset_id = str(asset.get("AssetID"))
    quantity = float(asset.get("Quantity") or 0)
    unit = str(asset.get("Unit", "units"))
    price = as_int(asset.get("CurrentPrice"))
    value = as_int(asset.get("CurrentValue"))
    cost = int(round(quantity * as_int(asset.get("AvgCost"))))
    unrealized = value - cost
    tone = "fin-good" if unrealized >= 0 else "fin-bad"
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2.3, 1.15, 1.15, 1.15])
        c1.markdown(
            f"**{esc(asset.get('Name', 'Unnamed'))}**  \n"
            f"<span class='fin-muted'>"
            f"{esc(ASSET_TYPE_LABELS.get(str(asset.get('AssetType', '')).lower(), asset.get('AssetType', '')))}"
            f" · {quantity:g} {esc(unit)}"
            + (f" · {esc(asset.get('Symbol'))}" if str(asset.get('Symbol', '')).strip() else "")
            + "</span>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            f"<div class='mono' style='font-size:1.02rem'>{money(value)}</div>"
            f"<div class='fin-muted' style='font-size:0.72rem'>current value</div>",
            unsafe_allow_html=True,
        )
        c3.markdown(
            f"<div class='mono' style='font-size:1.02rem'>{money(price)}</div>"
            f"<div class='fin-muted' style='font-size:0.72rem'>price per {esc(unit)}</div>",
            unsafe_allow_html=True,
        )
        c4.markdown(
            f"<div class='mono {tone}' style='font-size:1.02rem'>{money(unrealized, signed=True)}</div>"
            f"<div class='fin-muted' style='font-size:0.72rem'>unrealized</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Update valuation"):
            v1, v2 = st.columns([1, 1])
            new_price = v1.number_input(
                "Price per unit (₹)",
                min_value=0.0,
                value=from_paise(price),
                step=1.0,
                format="%.2f",
                key=f"val_price_{asset_id}",
            )
            when = v2.date_input(
                "Valuation date",
                value=date.today(),
                max_value=date.today(),
                key=f"val_date_{asset_id}",
            )
            st.caption(
                f"Cost basis {money(cost)} · valuation {str(asset.get('ValuationDate', ''))[:10] or '—'}"
            )
            if st.button("Review valuation", key=f"val_review_{asset_id}"):
                queue_plan(
                    "valuation",
                    {
                        "user": user,
                        "asset_id": asset_id,
                        "price_paise": to_paise(new_price),
                        "valuation_date": when,
                    },
                    [
                        ("Action", "Update valuation"),
                        ("Holding", asset_label(asset)),
                        ("New price", money(to_paise(new_price))),
                        ("Quantity", f"{quantity:g} {unit}"),
                        ("New value", money(int(round(quantity * to_paise(new_price))))),
                        ("Date", str(when)),
                    ],
                )


def _trade_rows(user: str, assets: dict[str, dict]) -> pd.DataFrame:
    frame = read_tab("InvestmentLedger")
    if frame.empty:
        return pd.DataFrame()
    rows = [
        row
        for row in frame.to_dict("records")
        if str(row.get("User", "")).strip() == user
    ]
    rows.sort(key=lambda row: (str(row.get("Date", "")), str(row.get("Timestamp", ""))), reverse=True)
    display = []
    for row in rows:
        asset = assets.get(str(row.get("AssetID", "")).strip(), {})
        display.append(
            {
                "Date": str(row.get("Date", ""))[:10],
                "Holding": asset.get("Name", row.get("AssetID", "")),
                "Book": str(row.get("Book", "")).title(),
                "Side": str(row.get("Side", "")).title(),
                "Quantity": f"{float(row.get('Quantity') or 0):g}",
                "Unit price": money(row.get("UnitPrice")),
                "Fees": money(row.get("Fees")),
                "Net": money(row.get("NetAmount")),
                "Realized": money(row.get("RealizedGain"), signed=True),
                "Status": str(row.get("Status", "")).title(),
            }
        )
    return pd.DataFrame(display)


def render() -> None:
    user = st.session_state.get("current_user")
    if not user:
        st.error("Select a profile in the sidebar.")
        return

    page_header(
        "Holdings",
        "Trade history is separate from cash. The holdings table is a rebuildable cache.",
        "portfolio",
    )
    all_rows = list_assets(user, active_only=False)
    active_rows = [row for row in all_rows if str(row.get("IsActive", "TRUE")).lower() != "false"]
    totals = _holding_totals(active_rows)
    stats_grid(
        [
            {"label": "Portfolio value", "value": money(totals["value"])},
            {"label": "Cost basis", "value": money(totals["cost"])},
            {
                "label": "Unrealized",
                "value": money(totals["unrealized"], signed=True),
                "tone": "good" if totals["unrealized"] >= 0 else "bad",
            },
            {
                "label": "Realized",
                "value": money(totals["realized"], signed=True),
                "tone": "good" if totals["realized"] >= 0 else "bad",
            },
        ]
    )

    investments = [
        row for row in active_rows if str(row.get("AssetType", "")).lower() not in {
            "real_estate", "gold", "vehicle", "other"
        }
    ]
    physical = [
        row for row in active_rows if str(row.get("AssetType", "")).lower() in {
            "real_estate", "gold", "vehicle", "other"
        }
    ]
    assets = {str(row.get("AssetID")): row for row in all_rows}

    tab_inv, tab_phys, tab_trades, tab_maint = st.tabs(
        ["Investments", "Physical assets", "Trade history", "Maintenance"]
    )
    with tab_inv:
        if not investments:
            empty_state("No stock, mutual fund or other financial holdings yet.")
        for asset in investments:
            _holding_block(asset, user, "inv")
    with tab_phys:
        if not physical:
            empty_state("No physical assets yet.")
        for asset in physical:
            _holding_block(asset, user, "phys")
    with tab_trades:
        trades = _trade_rows(user, assets)
        if trades.empty:
            empty_state("No trades yet.")
        else:
            st.dataframe(trades, hide_index=True, width="stretch")
    with tab_maint:
        st.caption(
            "Rebuild quantity, average cost, value and realized gain from posted trade rows. "
            "Safe to run after a reversal or if a holdings edit failed."
        )
        if st.button("Rebuild holdings from trade history", key="rebuild_assets"):
            try:
                result = rebuild_assets(user)
                st.toast(
                    f"Rebuilt {result.get('assets', 0)} holdings from {result.get('trades', 0)} trades.",
                    icon="✅",
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        st.markdown("---")
        st.caption(
            "Valuations are manual in this build. Use Update valuation on a holding to change "
            "its current price; the change is confirmed before it is saved."
        )
