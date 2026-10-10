"""Spec §7.5: what was incurred inside one month, and how each machine's hours were spent."""
import datetime as dt
from dataclasses import dataclass, field
from fractions import Fraction

from .intervals import Interval, hours, intersect, measure, merge, subtract
from .labour import IST, Labour, run_interval, shift_window
from .records import Downtime, Machine, Roll, RollRun, Run, Shift, WriteOff, YarnMove


def month_window(year: int, month: int) -> tuple[dt.date, dt.date, Interval]:
    """First day, first day of the next month, and the instants 00:00 IST to 00:00 IST."""
    first = dt.date(year, month, 1)
    after = dt.date(year + (month == 12), month % 12 + 1, 1)
    return first, after, (dt.datetime.combine(first, dt.time(), tzinfo=IST), dt.datetime.combine(after, dt.time(), tzinfo=IST))


@dataclass
class MonthCosts:
    per_order: dict[int, dict[str, Fraction]] = field(default_factory=dict)   # order id -> yarn / machine / labour
    yarn: Fraction = Fraction(0)
    machine: Fraction = Fraction(0)
    wages: Fraction = Fraction(0)       # pay of the attendance records dated in the month
    idle: Fraction = Fraction(0)
    support: Fraction = Fraction(0)
    writeoffs: Fraction = Fraction(0)

    @property
    def order_total(self) -> Fraction:
        return sum((sum(p.values(), Fraction(0)) for p in self.per_order.values()), Fraction(0))


def month_costs(first: dt.date, after: dt.date, span: Interval, runs: list[Run], machines: dict[int, Machine],
                moves: list[YarnMove], writeoffs: list[WriteOff], labour: Labour, now: dt.datetime) -> MonthCosts:
    out = MonthCosts()
    order_of = {r.id: r.order_id for r in runs}

    def bucket(order_id: int) -> dict[str, Fraction]:
        return out.per_order.setdefault(order_id, {"yarn": Fraction(0), "machine": Fraction(0), "labour": Fraction(0)})

    for move in moves:
        if span[0] <= move.at < span[1]:
            amount = -move.kg * move.cost_per_kg
            bucket(order_of[move.run_id])["yarn"] += amount
            out.yarn += amount
    for run in runs:
        if run.machine_id is None:
            continue
        lo, hi = run_interval(run, now)
        lo, hi = max(lo, span[0]), min(hi, span[1])
        if hi > lo:
            amount = hours(hi - lo) * machines[run.machine_id].rate
            bucket(run.order_id)["machine"] += amount
            out.machine += amount
    for rec in labour.records:
        if first <= rec.day < after:
            out.wages += rec.pay
            out.idle += rec.idle
            out.support += rec.support
            for run_id, share in rec.allocated.items():
                bucket(order_of[run_id])["labour"] += share
    for off in writeoffs:
        if span[0] <= off.at < span[1]:
            out.writeoffs += -off.kg * off.cost_per_kg
    return out


@dataclass
class MachineHours:
    running: Fraction
    idle: Fraction
    down: Fraction
    output: Fraction


def shift_time(shifts: list[Shift], span: Interval) -> list[Interval]:
    """Every shift window that touches the span, joined together, then cut to the span."""
    day = span[0].astimezone(IST).date() - dt.timedelta(days=1)
    last = span[1].astimezone(IST).date()
    windows = []
    while day <= last:
        windows += [shift_window(day, s) for s in shifts]
        day += dt.timedelta(days=1)
    return intersect(merge(windows), [span])


def machine_hours(machine: Machine, runs: list[Run], downtimes: list[Downtime], rolls: list[Roll],
                  roll_runs: list[RollRun], shifts: list[Shift], span: Interval, now: dt.datetime) -> MachineHours:
    """Hours inside shift time, from the month's start (or the machine's creation) to the month's end (or now)."""
    lo, hi = max(span[0], machine.created_at), min(span[1], now)
    if hi <= lo:
        return MachineHours(Fraction(0), Fraction(0), Fraction(0), Fraction(0))
    allowed = shift_time(shifts, (lo, hi))
    mine = [r for r in runs if r.machine_id == machine.id]
    down = intersect(merge([(d.start, d.end if d.end is not None else now) for d in downtimes
                            if d.machine_id == machine.id]), allowed)
    busy = intersect(merge([run_interval(r, now) for r in mine]), allowed)
    running = subtract(busy, down)
    total, d, r = measure(allowed), measure(down), measure(running)
    return MachineHours(running=r, idle=total - d - r, down=d, output=_output(machine, mine, rolls, roll_runs, (lo, hi)))


def _output(machine: Machine, mine: list[Run], rolls: list[Roll], roll_runs: list[RollRun],
            span: Interval) -> Fraction:
    """Spinning: kg of runs that ended in the span. Weaving: metres of rolls made in it.
    Dyeing: metres of rolls in dye runs that ended in it."""
    def inside(moment: dt.datetime | None) -> bool:
        return moment is not None and span[0] <= moment < span[1]

    if machine.stage == "spinning":
        return sum((r.output_kg or Fraction(0) for r in mine if inside(r.end)), Fraction(0))
    by_run = {r.id: r for r in mine}
    by_roll = {r.id: r for r in rolls}
    total = Fraction(0)
    for link in roll_runs:
        run, roll = by_run.get(link.run_id), by_roll.get(link.roll_id)
        if run is None or roll is None:
            continue
        if machine.stage == "weaving" and link.purpose == "produce" and inside(roll.made_at):
            total += roll.metres
        elif machine.stage == "dyeing" and link.purpose == "dye" and inside(run.end):
            total += roll.metres
    return total
