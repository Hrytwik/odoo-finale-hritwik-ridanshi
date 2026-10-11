"""Making, migrating and dropping the month's own database, and refusing every other name."""
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

API_DIR = Path(__file__).resolve().parents[2]
ALLOWED = {"everest_month", "everest_month_test", "everest_month_e2e"}      # the real one, and two for the tests


def database_name(url: str) -> str:
    return make_url(url).database or ""


def refuse_unless_allowed(url: str) -> None:
    if database_name(url) not in ALLOWED:
        sys.exit(f"Refused: this builds only {sorted(ALLOWED)}, not {database_name(url)!r}. Your own database is never touched.")


def _admin(url: str):
    return create_engine(make_url(url).set(database="postgres"), isolation_level="AUTOCOMMIT")


def drop(url: str) -> None:
    refuse_unless_allowed(url)
    admin = _admin(url)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name(url)}" WITH (FORCE)'))
    admin.dispose()


def recreate(url: str) -> None:
    refuse_unless_allowed(url)
    drop(url)
    admin = _admin(url)
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{database_name(url)}"'))
    admin.dispose()


def migrate(url: str) -> None:
    refuse_unless_allowed(url)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
