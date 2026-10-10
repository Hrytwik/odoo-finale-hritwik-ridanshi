"""Small shared checks that turn bad input into the standard error shape (see app/core/errors.py)."""
from collections.abc import Callable
from decimal import Decimal

from app.core.errors import AppError
from app.core.money import dec


def not_found(what: str, field: str | None = None) -> AppError:
    return AppError("NOT_FOUND", f"{what} not found", field=field, status=404)


def invalid(message: str, field: str) -> AppError:
    return AppError("VALIDATION_ERROR", message, field=field, status=422)


def exact_positive(value, field: str, rounder: Callable[[Decimal], Decimal]) -> Decimal:
    """A request number as an exact Decimal, rounded half up by `rounder`; refuses anything that rounds to zero or less."""
    try:
        d = rounder(dec(value))
    except ValueError:
        raise invalid("Enter a valid number", field) from None
    if d <= 0:
        raise invalid("This rounds to zero; enter a larger number", field)
    return d
