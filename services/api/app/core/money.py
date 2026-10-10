"""Exact arithmetic for quantities and money. Floats are only ever used at the JSON edge."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_KG = Decimal("0.001")
_MONEY = Decimal("0.01")
_MAX_MAGNITUDE = 15  # digits before the decimal point; rejects things like 1e999999


def dec(value) -> Decimal:
    """Turn a request value into a finite Decimal. Floats are read as the number that was printed (0.1, not 0.1000000000000000055)."""
    if value is None or isinstance(value, bool):
        raise ValueError("not a number")
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value))
        except InvalidOperation:
            raise ValueError("not a number") from None
    if not d.is_finite() or d.adjusted() >= _MAX_MAGNITUDE:
        raise ValueError("not a usable number")
    return d


def q_kg(d: Decimal) -> Decimal:
    return d.quantize(_KG, rounding=ROUND_HALF_UP)


def q_money(d: Decimal) -> Decimal:
    return d.quantize(_MONEY, rounding=ROUND_HALF_UP)


def to_float(d: Decimal) -> float:
    return float(d)
