"""Builds `everest_month`: 30 days of mill history, ending an hour before now, through the real services.

    npm run db:month         (from the repository root)

It creates the database itself (dropping and recreating only that one), migrates it, loads the starter data, plays the
month and prints the audit. It refuses any other database name, so `everest` can never be touched.
"""
import datetime as dt
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts import seed_dev
from scripts.month import database
from scripts.month.audit import Check, audit, report
from scripts.month.clock import SimClock
from scripts.month.plan import IST, build_plan
from scripts.month.runner import Runner

DEFAULT_URL = "postgresql+psycopg://localhost:5432/everest_month"
SAFETY_GAP = dt.timedelta(minutes=2)      # every real step happens after the build starts; the whole build takes seconds


def choose_end(now: dt.datetime) -> dt.datetime:
    """The simulated month ends five minutes before now, rounded down to the minute: every real timestamp is then later
    than every simulated one, and the mill on screen is as fresh as the build."""
    return (now.astimezone(IST) - dt.timedelta(minutes=5)).replace(second=0, microsecond=0)


def build_month(url: str, end: dt.datetime | None = None, days: int = 30, orders=None, seed: int = 11, full: bool = True,
                keep: bool = True) -> list[Check]:
    database.refuse_unless_allowed(url)
    now = dt.datetime.now(IST)
    end = end or choose_end(now)
    if end > now - SAFETY_GAP:
        sys.exit(f"Refused: the simulated month would end at {end:%d %b %H:%M}, too close to or after the real clock "
                 f"({now:%d %b %H:%M}); real and simulated timestamps would be indistinguishable.")
    database.recreate(url)
    database.migrate(url)
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            plan = build_plan(end, seed=seed, days=days, orders=orders)
            clock = SimClock(db, end)
            with clock.installed():
                with clock.at(plan.day0 - dt.timedelta(days=6)):
                    seed_dev.seed_all(db)
                runner = Runner(db, clock)
                runner.play(plan.events)
            return audit(db, clock, runner=runner, full=full)
    finally:
        engine.dispose()
        if not keep:
            database.drop(url)


def main() -> None:
    url = os.environ.get("MONTH_DATABASE_URL", DEFAULT_URL)
    checks = build_month(url)
    print(report(checks))
    sys.exit(0 if all(c.ok for c in checks) else 1)


if __name__ == "__main__":
    main()
