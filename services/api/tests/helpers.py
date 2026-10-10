from contextlib import contextmanager

import pytest
from sqlalchemy.exc import IntegrityError


@contextmanager
def violates(constraint: str):
    """Expect the block to fail on exactly this named database constraint, not just on any integrity error."""
    with pytest.raises(IntegrityError) as exc:
        yield
    fired = exc.value.orig.diag.constraint_name
    assert fired == constraint, f"expected constraint {constraint!r} to fire, but {fired!r} did"
