"""Spec §8.1: when will each open order be delivered? Earliest-deadline-first at every stage, one pool of capacity per
stage. Pure: no database, no clock; every quantity is an exact fraction and "days" are counted from today."""
import datetime as dt
import math
from dataclasses import dataclass, field
from fractions import Fraction

STAGES = ("spinning", "weaving", "dyeing")
ORDINALS = {2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth"}


@dataclass(frozen=True)
class OpenOrder:
    code: str
    deadline: dt.date
    confirmed_at: dt.datetime
    work: dict[str, Fraction]       # remaining spinning kg, weaving m, dyeing m
    fully_passed: bool = False      # every ordered metre has already passed QC: no QC day to wait for


@dataclass(frozen=True)
class StageCapacity:
    rate_per_hour: Fraction                 # sum of rated output x efficiency over the stage's machines that are up
    shift_hours: tuple[Fraction, ...]       # the length of every configured shift, in order
    shifts_run: int                         # how many of them (the first ones) this stage runs

    def per_day(self, shifts: int | None = None) -> Fraction:
        return self.rate_per_hour * sum(self.shift_hours[: self.shifts_run if shifts is None else shifts], Fraction(0))

    @property
    def can_add_shift(self) -> bool:
        return self.shifts_run < len(self.shift_hours)


@dataclass(frozen=True)
class EffRun:
    stage: str
    hours: Fraction
    rated: Fraction
    output: Fraction


def observed_efficiency(runs: list[EffRun], default: Fraction = Fraction(4, 5),
                        min_hours: Fraction = Fraction(1)) -> dict[str, Fraction]:
    """Output over rated output across a stage's recently ended runs, capped at 1; with too little run time to judge
    (or nothing rated), the default."""
    out = {}
    for stage in STAGES:
        mine = [r for r in runs if r.stage == stage]
        hours = sum((r.hours for r in mine), Fraction(0))
        rated = sum((r.hours * r.rated for r in mine), Fraction(0))
        out[stage] = default if hours < min_hours or rated == 0 else min(Fraction(1), sum((r.output for r in mine), Fraction(0)) / rated)
    return out


def queue_order(orders: list[OpenOrder], front: str | None = None) -> list[OpenOrder]:
    """Earliest deadline first (ties: confirmed earlier, then code); `front` puts one order first at every stage."""
    ordered = sorted(orders, key=lambda o: (o.deadline, o.confirmed_at, o.code))
    if front is not None:
        ordered = [o for o in ordered if o.code == front] + [o for o in ordered if o.code != front]
    return ordered


@dataclass
class Plan:
    finish: dict[str, dict[str, Fraction | None]]       # order -> stage -> day (from today) its work there is done
    added: dict[str, dict[str, Fraction | None]]        # order -> stage -> days that stage added to its wait
    delivery: dict[str, dt.date | None]


def make_plan(orders: list[OpenOrder], capacity: dict[str, Fraction], today: dt.date, qc_days: int = 1,
              dispatch_days: int = 1, front: str | None = None) -> Plan:
    """An order with no work left at a stage passes straight through it. Otherwise it finishes when the work queued
    ahead of it (and its own) is cleared, but never before it finished the previous stage. No capacity: None."""
    queue = queue_order(orders, front)
    finish: dict[str, dict[str, Fraction | None]] = {o.code: {} for o in queue}
    added: dict[str, dict[str, Fraction | None]] = {o.code: {} for o in queue}
    for number, stage in enumerate(STAGES):
        cumulative = Fraction(0)
        for order in queue:
            previous = finish[order.code][STAGES[number - 1]] if number else Fraction(0)
            work = order.work[stage]
            cumulative += work
            if work == 0:
                finish[order.code][stage], added[order.code][stage] = previous, Fraction(0)
            elif capacity[stage] == 0 or previous is None:
                finish[order.code][stage] = added[order.code][stage] = None
            else:
                done = cumulative / capacity[stage]
                finish[order.code][stage] = max(previous, done)
                added[order.code][stage] = max(Fraction(0), done - previous)
    delivery: dict[str, dt.date | None] = {}
    for order in orders:
        last = finish[order.code]["dyeing"]
        extra = dispatch_days + (0 if order.fully_passed else qc_days)
        delivery[order.code] = None if last is None else today + dt.timedelta(days=math.ceil(last) + extra)
    return Plan(finish, added, delivery)


@dataclass(frozen=True)
class WhatIf:
    kind: str                   # add_shift / move_to_front
    label: str
    delivery: dt.date
    days_late: int


@dataclass(frozen=True)
class Eta:
    code: str
    deadline: dt.date
    delivery: dt.date
    days_late: int
    bottleneck: str | None
    stage_dates: dict[str, dt.date]
    what_ifs: list[WhatIf] = field(default_factory=list)


def days_late(order: OpenOrder, delivery: dt.date) -> int:
    return max(0, (delivery - order.deadline).days)


def _day(days: Fraction, today: dt.date) -> dt.date:
    return today + dt.timedelta(days=math.ceil(days))


def _harm(others: list[OpenOrder], before: Plan, after: Plan) -> str:
    worse = []
    for other in others:
        was, now = before.delivery[other.code], after.delivery[other.code]
        if was is not None and now is not None and days_late(other, now) > days_late(other, was):
            worse.append((days_late(other, now), other.code))
    worse.sort(key=lambda w: (-w[0], w[1]))
    if not worse:
        return ""
    parts = [f"{code} would be {n} day{'s' if n != 1 else ''} late" for n, code in worse[:3]]
    if len(worse) > 3:
        parts.append(f"and {len(worse) - 3} more")
    return " (" + ", ".join(parts) + ")"


def all_etas(orders: list[OpenOrder], stages: dict[str, StageCapacity], today: dt.date, qc_days: int = 1,
             dispatch_days: int = 1, only: str | None = None, with_what_ifs: bool = True) -> dict[str, Eta | None]:
    """One entry per order; None when its date is unknown (a stage with work and no working machine). What-ifs are
    worked out for late orders only (or just for `only`, or for none with `with_what_ifs=False`), and only the ones
    that strictly improve the date."""
    capacity = {stage: stages[stage].per_day() for stage in STAGES}
    base = make_plan(orders, capacity, today, qc_days, dispatch_days)
    out: dict[str, Eta | None] = {}
    for order in orders:
        delivery = base.delivery[order.code]
        if delivery is None:
            out[order.code] = None
            continue
        late = days_late(order, delivery)
        added = base.added[order.code]
        bottleneck = max(STAGES, key=lambda s: (added[s], -STAGES.index(s))) if late else None
        eta = Eta(order.code, order.deadline, delivery, late, bottleneck,
                  {s: _day(base.finish[order.code][s], today) for s in STAGES})
        if late and with_what_ifs and (only is None or only == order.code):
            stage = stages[bottleneck]
            if stage.can_add_shift:
                bigger = {**capacity, bottleneck: stage.per_day(stage.shifts_run + 1)}
                plan = make_plan(orders, bigger, today, qc_days, dispatch_days)
                if plan.delivery[order.code] is not None and plan.delivery[order.code] < delivery:
                    n = stage.shifts_run + 1
                    eta.what_ifs.append(WhatIf("add_shift", f"Add a {ORDINALS.get(n, f'{n}th')} shift on {bottleneck}",
                                               plan.delivery[order.code], days_late(order, plan.delivery[order.code])))
            plan = make_plan(orders, capacity, today, qc_days, dispatch_days, front=order.code)
            if plan.delivery[order.code] is not None and plan.delivery[order.code] < delivery:
                label = f"Move {order.code} to the front of every queue" + _harm(
                    [o for o in orders if o.code != order.code], base, plan)
                eta.what_ifs.append(WhatIf("move_to_front", label, plan.delivery[order.code],
                                           days_late(order, plan.delivery[order.code])))
        out[order.code] = eta
    return out
