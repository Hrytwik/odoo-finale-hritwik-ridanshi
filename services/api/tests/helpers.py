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


def wipe_database(engine) -> None:
    """Empty every table after a test that had to commit real data (concurrency tests use separate sessions)."""
    from sqlalchemy import text

    with engine.begin() as conn:
        names = [r[0] for r in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"))]
        conn.execute(text("TRUNCATE " + ", ".join(f'"{n}"' for n in names) + " RESTART IDENTITY CASCADE"))
