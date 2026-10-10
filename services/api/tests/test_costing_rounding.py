"""Rounding at the edge: the engine is exact, the response is rounded half up to the paisa."""
from decimal import Decimal
from fractions import Fraction as F

from app.modules.costing.service import money, two_places


def test_money_rounds_half_up_to_the_paisa():
    assert money(F(1, 200)) == Decimal("0.01")                       # exactly half a paisa goes up
    assert money(F(1, 3)) == Decimal("0.33") and money(F(2, 3)) == Decimal("0.67")
    assert money(F(800, 3)) == Decimal("266.67") and money(F(0)) == 0
    assert money(F(-1, 200)) == Decimal("-0.01")


def test_a_total_is_the_sum_of_its_rounded_parts_which_is_why_it_can_differ_from_the_rounded_exact_total():
    third = money(F(800, 3))
    assert third * 3 == Decimal("800.01")                            # three rounded thirds are a paisa over 800
    assert money(F(800)) == Decimal("800.00")


def test_hours_and_quantities_show_two_places():
    assert two_places(F(1, 3)) == 0.33 and two_places(F(5, 3)) == 1.67 and two_places(F(1, 200)) == 0.01
