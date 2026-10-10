"""Time intervals as (start, end) pairs of aware datetimes, measured in exact hours."""
import datetime as dt
from fractions import Fraction

Interval = tuple[dt.datetime, dt.datetime]
_MICROS_PER_HOUR = 3600 * 10**6


def hours(delta: dt.timedelta) -> Fraction:
    micros = (delta.days * 86400 + delta.seconds) * 10**6 + delta.microseconds
    return Fraction(micros, _MICROS_PER_HOUR)


def merge(intervals: list[Interval]) -> list[Interval]:
    """Sorted, with overlapping or touching intervals joined and empty ones dropped."""
    out: list[Interval] = []
    for lo, hi in sorted(i for i in intervals if i[1] > i[0]):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def intersect(xs: list[Interval], ys: list[Interval]) -> list[Interval]:
    """Both lists must already be merged."""
    out: list[Interval] = []
    i = j = 0
    while i < len(xs) and j < len(ys):
        lo, hi = max(xs[i][0], ys[j][0]), min(xs[i][1], ys[j][1])
        if hi > lo:
            out.append((lo, hi))
        if xs[i][1] < ys[j][1]:
            i += 1
        else:
            j += 1
    return out


def subtract(xs: list[Interval], ys: list[Interval]) -> list[Interval]:
    """What is in xs but not in ys. Both lists must already be merged."""
    out: list[Interval] = []
    for lo, hi in xs:
        cur = lo
        for ylo, yhi in ys:
            if yhi <= cur or ylo >= hi:
                continue
            if ylo > cur:
                out.append((cur, ylo))
            cur = max(cur, yhi)
        if cur < hi:
            out.append((cur, hi))
    return out


def measure(intervals: list[Interval]) -> Fraction:
    return sum((hours(hi - lo) for lo, hi in intervals), Fraction(0))


def overlap_hours(a: Interval, b: Interval) -> Fraction:
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return hours(hi - lo) if hi > lo else Fraction(0)
