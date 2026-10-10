from decimal import Decimal

import pytest

from app.core.money import dec, q_kg, q_money, to_float


def test_dec_uses_the_printed_value_not_the_binary_float():
    assert dec(0.1) == Decimal("0.1")
    assert dec("12.3456") == Decimal("12.3456")
    assert dec(5) == Decimal("5")
    assert dec(Decimal("1.5")) == Decimal("1.5")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, False, "abc", "", None, "1e999999"])
def test_dec_rejects_values_that_are_not_finite_numbers(bad):
    with pytest.raises(ValueError):
        dec(bad)


def test_quantities_round_half_up_to_three_places():
    assert q_kg(Decimal("1.0005")) == Decimal("1.001")
    assert q_kg(Decimal("1.0004")) == Decimal("1.000")
    assert q_kg(Decimal("587.5")) == Decimal("587.500")


def test_money_rounds_half_up_to_two_places():
    assert q_money(Decimal("2.675")) == Decimal("2.68")
    assert q_money(Decimal("200000")) == Decimal("200000.00")


def test_to_float_is_only_for_the_json_edge():
    assert to_float(Decimal("212.500")) == 212.5
    assert isinstance(to_float(Decimal("1")), float)
