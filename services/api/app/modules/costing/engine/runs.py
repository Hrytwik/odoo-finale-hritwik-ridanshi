"""Spec §7.1: what one run costs: yarn, machine and labour."""
import datetime as dt
from dataclasses import dataclass
from fractions import Fraction

from .intervals import hours
from .labour import run_interval
from .records import Machine, Run, YarnMove


@dataclass
class RunCost:
    yarn: Fraction
    machine: Fraction
    labour: Fraction
    hours: Fraction

    @property
    def total(self) -> Fraction:
        return self.yarn + self.machine + self.labour


def run_costs(runs: list[Run], machines: dict[int, Machine], moves: list[YarnMove],
              labour_per_run: dict[int, Fraction], now: dt.datetime) -> dict[int, RunCost]:
    """Yarn: kg issued minus kg returned times the lot's cost per kg (an issue is stored negative).
    Machine: hours times the machine's rate; a run with no machine (hand mending) costs 0 here."""
    yarn: dict[int, Fraction] = {}
    for move in moves:
        yarn[move.run_id] = yarn.get(move.run_id, Fraction(0)) - move.kg * move.cost_per_kg
    out: dict[int, RunCost] = {}
    for run in runs:
        lo, hi = run_interval(run, now)
        h = hours(hi - lo)
        machine = machines[run.machine_id] if run.machine_id is not None else None
        out[run.id] = RunCost(
            yarn=yarn.get(run.id, Fraction(0)), machine=h * machine.rate if machine else Fraction(0),
            labour=labour_per_run.get(run.id, Fraction(0)), hours=h)
    return out
