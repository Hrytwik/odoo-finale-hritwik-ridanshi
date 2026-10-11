"""The simulated clock for the month build.

The services take "now" from the database clock (`db_now`), from a database default (`DEFAULT now()`), from Python
(`datetime.now`) and, for dates, from `today_ist()`. Around every simulated step this clock records the real time, lets the
service run, then rewrites every timestamp-with-time-zone value written in that real window to exactly the simulated moment
(a simulated step is instantaneous: keeping the few milliseconds a step really took would put a hand-over planned for
14:00:00 at 14:00:00.012, a hair outside the outgoing operator's shift, which the costing reports as uncovered hours), and
answers `today_ist()` with the simulated date. It works only because simulated history ends before the real clock: a
simulated value can never fall inside a later real window.
"""
import datetime as dt
import sys
from contextlib import contextmanager

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core import clock as core_clock

MARGIN = dt.timedelta(seconds=0.25)     # a transaction's `now()` is its start, a hair before the first query's clock reading


def timestamp_columns(db: Session) -> dict[str, list[str]]:
    """Every timestamp-with-time-zone column of every real table (views excluded), by table: asked of the database,
    so a column added later is covered without anyone remembering to list it."""
    rows = db.execute(text(
        "SELECT c.table_name, c.column_name FROM information_schema.columns c "
        "JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name "
        "WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE' AND c.data_type = 'timestamp with time zone' "
        "ORDER BY c.table_name, c.ordinal_position")).all()
    out: dict[str, list[str]] = {}
    for table, column in rows:
        out.setdefault(table, []).append(column)
    return out


class SimClock:
    def __init__(self, db: Session, end: dt.datetime):
        self.db, self.end, self.now = db, end, end
        self.columns = timestamp_columns(db)

    def real_now(self) -> dt.datetime:
        return self.db.scalar(select(func.clock_timestamp()))

    @contextmanager
    def installed(self):
        """Inside this block `today_ist()` answers with the simulated date, in every loaded `app` module that imported it."""
        original = core_clock.today_ist
        patched = lambda: self.now.astimezone(core_clock.IST).date()  # noqa: E731
        touched = [m for name, m in list(sys.modules.items()) if name.startswith("app.") and getattr(m, "today_ist", None) is original]
        for module in touched:
            module.today_ist = patched
        core_clock.today_ist = patched
        try:
            yield self
        finally:
            for module in touched:
                module.today_ist = original
            core_clock.today_ist = original

    @contextmanager
    def at(self, moment: dt.datetime):
        """One simulated step. Whatever real timestamps the body writes become exactly `moment`."""
        real_start = self.real_now()
        self.now = moment
        yield
        self._move(real_start, self.real_now(), moment)
        self.db.commit()

    def _move(self, real_start: dt.datetime, real_end: dt.datetime, moment: dt.datetime) -> None:
        params = {"lo": real_start - MARGIN, "hi": real_end + MARGIN, "moment": moment}
        for table, columns in self.columns.items():
            # one statement per table, so a row's two columns (started_at and ended_at) move together and a CHECK between
            # them is judged on the final values
            sets = ", ".join(f'"{c}" = CASE WHEN "{c}" BETWEEN :lo AND :hi THEN :moment ELSE "{c}" END'
                             for c in columns)
            where = " OR ".join(f'"{c}" BETWEEN :lo AND :hi' for c in columns)
            self.db.execute(text(f'UPDATE "{table}" SET {sets} WHERE {where}'), params)

    def leaks(self) -> list[str]:
        """Every column holding a value later than the simulated end: a real-clock value that was never moved."""
        out = []
        for table, columns in self.columns.items():
            for column in columns:
                n = self.db.scalar(text(f'SELECT count(*) FROM "{table}" WHERE "{column}" > :end'), {"end": self.end})
                if n:
                    out.append(f"{table}.{column}: {n} value(s) later than {self.end:%Y-%m-%d %H:%M}")
        return out
