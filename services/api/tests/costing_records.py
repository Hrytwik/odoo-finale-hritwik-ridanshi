"""Short builders for the engine's plain records, so a test reads like the hand-worked case it asserts."""
import datetime as dt
from fractions import Fraction

from app.modules.costing.engine.labour import IST
from app.modules.costing.engine.records import (
    Attendance, Machine, Roll, RollRun, Run, Shift, Worker, YarnMove,
)

A = Shift(1, "A", dt.time(6), dt.time(14))        # 8 hours
B = Shift(2, "B", dt.time(14), dt.time(22))       # 8 hours
C = Shift(3, "C", dt.time(22), dt.time(6))        # 8 hours, crosses midnight
SHIFTS = {s.id: s for s in (A, B, C)}


def at(day: int, hour: int, minute: int = 0, month: int = 10) -> dt.datetime:
    return dt.datetime(2026, month, day, hour, minute, tzinfo=IST)


def worker(id: int, role: str = "operator", wage: int = 800) -> Worker:
    return Worker(id, role, Fraction(wage))


def present(worker_id: int, day: int, shift: Shift = A, status: str = "present", month: int = 10) -> Attendance:
    return Attendance(worker_id, dt.date(2026, month, day), shift.id, status)


def run(id: int, operator: int, start: dt.datetime, end: dt.datetime | None, order: int = 1, stage: str = "weaving",
        machine: int | None = 1, output_kg=None) -> Run:
    return Run(id, order, machine, stage, operator, start, end, None if output_kg is None else Fraction(output_kg))


def machine(id: int = 1, stage: str = "weaving", rate: int = 60, rated: int = 20,
            created: dt.datetime | None = None) -> Machine:
    return Machine(id, f"M-{id}", f"Machine {id}", stage, Fraction(rated), Fraction(rate), created or at(1, 0, month=9))


def roll(id: int, metres: int, rejected: bool = False, settled: bool = True, order: int = 1,
         made: dt.datetime | None = None) -> Roll:
    return Roll(id, order, Fraction(metres), rejected, settled, made or at(5, 12))


def link(roll_id: int, run_id: int, purpose: str = "produce") -> RollRun:
    return RollRun(roll_id, run_id, purpose)


def issue(run_id: int, kg: int, cost: int, when: dt.datetime | None = None) -> YarnMove:
    return YarnMove(run_id, Fraction(-kg), Fraction(cost), when or at(3, 8))
