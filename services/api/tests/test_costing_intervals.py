"""The time-interval helpers behind the shift windows and machine hours."""
import datetime as dt
from fractions import Fraction as F

from app.modules.costing.engine.intervals import hours, intersect, measure, merge, overlap_hours, subtract
from tests.costing_records import at


def test_hours_are_exact_down_to_the_microsecond():
    assert hours(dt.timedelta(hours=8)) == 8
    assert hours(dt.timedelta(minutes=20)) == F(1, 3)
    assert hours(dt.timedelta(microseconds=1)) == F(1, 3600 * 10**6)


def test_merge_joins_overlapping_and_touching_intervals_and_drops_empty_ones():
    assert merge([(at(1, 8), at(1, 10)), (at(1, 9), at(1, 12)), (at(1, 12), at(1, 13)), (at(1, 15), at(1, 15))]) \
        == [(at(1, 8), at(1, 13))]
    assert merge([(at(1, 15), at(1, 16)), (at(1, 8), at(1, 9))]) == [(at(1, 8), at(1, 9)), (at(1, 15), at(1, 16))]


def test_intersect_and_subtract():
    xs, ys = [(at(1, 8), at(1, 12)), (at(1, 14), at(1, 18))], [(at(1, 10), at(1, 15))]
    assert intersect(xs, ys) == [(at(1, 10), at(1, 12)), (at(1, 14), at(1, 15))]
    assert subtract(xs, ys) == [(at(1, 8), at(1, 10)), (at(1, 15), at(1, 18))]
    assert subtract(xs, []) == xs and subtract([], ys) == [] and intersect(xs, []) == []


def test_measure_and_overlap():
    assert measure([(at(1, 8), at(1, 10)), (at(1, 14), at(1, 15))]) == 3
    assert overlap_hours((at(1, 8), at(1, 12)), (at(1, 10), at(1, 20))) == 2
    assert overlap_hours((at(1, 8), at(1, 10)), (at(1, 10), at(1, 20))) == 0         # touching is not overlapping
