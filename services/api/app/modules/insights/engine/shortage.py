"""Spec §8.2: when does a yarn type fall below its reorder level, and when must the next order be placed?"""
import datetime as dt
import math
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Demand:
    order_code: str
    outstanding_kg: Fraction     # yarn this order still has to draw from stock
    window_days: int             # the days over which that draw is spread (its spinning window, at least 1)


@dataclass(frozen=True)
class Forecast:
    free_kg: Fraction
    falls_below_on: dt.date | None
    order_by: dt.date | None
    suggested_kg: Fraction
    overdue_days: int


def spinning_window(finish_days: Fraction | None) -> int:
    """Whole days from today to the end of an order's spinning, at least one. No spinning capacity: draw it all at once."""
    return 1 if finish_days is None else max(1, math.ceil(finish_days))


def round_up(kg: Fraction, step: int) -> Fraction:
    return Fraction(math.ceil(kg / step) * step)


def forecast(on_hand_kg: Fraction, reorder_level_kg: Fraction, demands: list[Demand], lead_time_days: int | None,
             today: dt.date, round_kg: int = 50) -> Forecast | None:
    """None when the yarn never falls below its reorder level. Stock only goes down (each order draws its outstanding
    yarn evenly over its window), so it ends at on_hand - total outstanding = free_kg; the day-by-day walk finds WHEN."""
    outstanding = sum((d.outstanding_kg for d in demands), Fraction(0))
    free = on_hand_kg - outstanding
    if free >= reorder_level_kg:
        return None
    falls = today if on_hand_kg < reorder_level_kg else None
    for day in range(1, max((d.window_days for d in demands), default=0) + 1):
        if falls is not None:
            break
        stock = on_hand_kg - sum(d.outstanding_kg * min(day, d.window_days) / d.window_days for d in demands)
        if stock < reorder_level_kg:
            falls = today + dt.timedelta(days=day - 1)        # it happens during that day
    order_by = None if lead_time_days is None or falls is None else falls - dt.timedelta(days=lead_time_days)
    return Forecast(free, falls, order_by, round_up(reorder_level_kg - free, round_kg),
                    max(0, (today - order_by).days) if order_by else 0)
