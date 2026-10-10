"""Plain records the engine works on. The loader (costing/loader.py) builds them from database rows."""
import datetime as dt
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Shift:
    id: int
    name: str
    start: dt.time
    end: dt.time          # earlier than or equal to start means the shift crosses midnight


@dataclass(frozen=True)
class Worker:
    id: int
    role: str             # 'operator' leftovers are idle labour, every other role's are support staff
    daily_wage: Fraction


@dataclass(frozen=True)
class Attendance:
    worker_id: int
    day: dt.date          # the day the shift STARTS
    shift_id: int
    status: str           # present / half_day / absent


@dataclass(frozen=True)
class Machine:
    id: int
    code: str
    name: str
    stage: str
    rated: Fraction       # rated output per hour (kg for spinning, metres otherwise)
    rate: Fraction        # running cost per hour
    created_at: dt.datetime


@dataclass(frozen=True)
class Run:
    id: int
    order_id: int
    machine_id: int | None
    stage: str            # spinning / weaving / dyeing / rework
    operator_id: int
    start: dt.datetime
    end: dt.datetime | None
    output_kg: Fraction | None = None


@dataclass(frozen=True)
class Roll:
    id: int
    order_id: int
    metres: Fraction
    rejected: bool        # latest verdict is reject
    settled: bool         # not woven, dyeing, awaiting QC, awaiting rework or in rework
    made_at: dt.datetime


@dataclass(frozen=True)
class RollRun:
    roll_id: int
    run_id: int
    purpose: str          # produce / dye / rework


@dataclass(frozen=True)
class YarnMove:
    run_id: int
    kg: Fraction          # signed: an issue is negative, a return positive
    cost_per_kg: Fraction
    at: dt.datetime


@dataclass(frozen=True)
class WriteOff:
    kg: Fraction          # a negative stock adjustment (stored negative)
    cost_per_kg: Fraction
    at: dt.datetime


@dataclass(frozen=True)
class Downtime:
    machine_id: int
    start: dt.datetime
    end: dt.datetime | None
