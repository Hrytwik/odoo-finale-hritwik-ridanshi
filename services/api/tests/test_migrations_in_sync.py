from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

import app.db.models  # noqa: F401  registers every table on Base.metadata
from app.db.base import Base


def test_migrations_build_exactly_what_the_models_declare(engine):
    """Fails when a model is changed but no migration was written for it.

    The test database is built by running the migrations, so without this check a forgotten
    migration would leave every other test green while the real database lags behind the models.
    (Alembic does not compare CHECK constraints, so those are covered by the per-table tests.)
    """
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []
