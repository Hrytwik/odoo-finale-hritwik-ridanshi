"""Small shared checks that turn bad input into the standard error shape (see app/core/errors.py)."""
import re
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


_UPLOAD_PATH = re.compile(r"uploads/[0-9a-f]{32}\.(jpg|png|webp)")


def check_upload_path(path: str, field: str) -> str:
    """A photo path must be one the upload endpoint handed out (never a free-typed path or URL); full match."""
    if _UPLOAD_PATH.fullmatch(path) is None:
        raise invalid("Use a photo uploaded through the app", field)
    return path
