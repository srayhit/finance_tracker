"""Money is stored as integer paise. One rounding helper for the whole app."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def to_paise(value: object) -> int:
    """Convert a rupee amount (float/string/Decimal) to integer paise."""
    if value is None or str(value).strip() == "":
        return 0
    try:
        amount = Decimal(str(value).replace(",", "")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except Exception:
        return 0
    return int(amount * 100)


def from_paise(paise: object) -> float:
    try:
        return int(paise or 0) / 100.0
    except (TypeError, ValueError):
        return 0.0


def format_inr(paise: object, signed: bool = False) -> str:
    """Indian grouping: ₹12,34,567.89."""
    amount = int(paise or 0)
    negative = amount < 0
    amount = abs(amount)
    rupees, paise_part = divmod(amount, 100)

    digits = str(rupees)
    if len(digits) <= 3:
        grouped = digits
    else:
        last3 = digits[-3:]
        rest = digits[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3

    text = f"₹{grouped}.{paise_part:02d}"
    if negative:
        text = f"-{text}"
    elif signed:
        text = f"+{text}"
    return text
