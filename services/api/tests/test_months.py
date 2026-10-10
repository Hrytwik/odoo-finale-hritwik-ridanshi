"""A month in a request is a real calendar month between 1900-01 and 2100-12; anything else is a 422 on `month`."""
import pytest
from app.core.errors import AppError
from app.core.validate import parse_month


def test_parse_month_returns_year_and_month():
    assert parse_month("2026-09") == (2026, 9) and parse_month("1900-01") == (1900, 1) and parse_month("2100-12") == (2100, 12)


@pytest.mark.parametrize("month", ["0000-01", "0001-12", "1899-12", "2101-01", "9999-12", "2026-13", "2026-00", "", "x"])
def test_parse_month_refuses_what_the_date_maths_cannot_handle(month):
    with pytest.raises(AppError) as error:
        parse_month(month)
    assert error.value.status == 422 and error.value.field == "month"
