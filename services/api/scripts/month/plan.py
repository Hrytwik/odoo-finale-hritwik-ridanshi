"""The month as a list of timed events: pure Python, no database, deterministic for a seed.

Every order is walked through the mill in creation order: spin on the first free ring frame, weave on two or three free
looms (a roll off about every 500 m), dye in batches on free dyers, inspect each roll, re-dye or mend the ones sent back,
load the passed rolls on trucks, confirm the trucks, and let the buyers pay later. Machines run round the clock and are
handed to a present operator at every shift change. Events later than `end` are dropped, so whatever is mid-way at
`end` is left open: that is the mill "right now".
"""
import datetime as dt
import math
import random
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from scripts.seed_dev import MACHINES

IST = ZoneInfo("Asia/Kolkata")
SHIFT_STARTS = (6, 14, 22)
RATE = {code: rate for code, _name, _stage, rate, _cost in MACHINES}
MACHINE_INDEX = {code: i for i, (code, *_rest) in enumerate(MACHINES)}
SPINNERS, DYERS = ["SPIN-01", "SPIN-02"], ["DYE-01", "DYE-02"]
LOOMS = [f"LOOM-{n:02d}" for n in range(1, 6)]                  # LOOM-06 is never planned: the idle machine
OPERATORS = {"A": ["W-001", "W-006", "W-007"], "B": ["W-008", "W-009"], "C": ["W-010", "W-011"]}
SUPPORT = ["W-002", "W-003", "W-004", "W-005", "W-012"]         # on the payroll, not running machines; marked in shift A
UNLUCKY = "W-009"                                               # a little more defective than the rest, but not flaggable
RECIPE = {                                                      # kg per metre, wastage, yarn code, supplier, cost range per kg
    "Poplin 58in": (0.12, 0.05, "30S-COT-RAW", "Vardhman Yarns", (245, 265)),
    "Twill 58in": (0.16, 0.04, "40S-PC-RAW", "Coastal Spinners", (272, 290)),
}
ODDS = {"normal": (0.88, 0.08, 0.04), "bad": (0.15, 0.55, 0.30), "loss": (0.15, 0.65, 0.20),    # pass, rework, reject
        "remake": (0.95, 0.05, 0.0)}                            # the replacement batch for rejected metres: never rejects
AFTER_REWORK = {"normal": [0.8, 0.2], "bad": [0.8, 0.2], "loss": [0.6, 0.4], "remake": [1.0, 0.0]}      # pass, reject
REDYE_SHARE = {"normal": 0.2, "bad": 0.2, "loss": 0.5, "remake": 0.2}         # of the reworked rolls, the share re-dyed (the rest mended by hand)
DEFECTS = {"normal": ["hole", "stain", "thread_fault"], "bad": ["thread_fault", "hole"], "loss": ["stain", "hole"],
           "remake": ["stain"]}
BREAKDOWNS = [("LOOM-06", 9, 10, 40, "belt snapped"), ("SPIN-01", 15, 11, 14, "bearing noise"),
              ("DYE-02", 22, 8, 20, "heater fault"), ("SPIN-02", 29, 20, 12, "drive belt slipping")]


def hours(x: float) -> dt.timedelta:
    return dt.timedelta(hours=x)


def minutes(x: float) -> dt.timedelta:
    return dt.timedelta(minutes=x)


def shift_of(t: dt.datetime) -> tuple[str, dt.date]:
    """The shift in effect at t and the date it is filed under (a night shift is dated by the day it starts)."""
    if 6 <= t.hour < 14:
        return "A", t.date()
    if 14 <= t.hour < 22:
        return "B", t.date()
    return "C", t.date() if t.hour >= 22 else t.date() - dt.timedelta(days=1)


def boundaries(start: dt.datetime, end: dt.datetime) -> list[dt.datetime]:
    """The shift changes strictly inside (start, end)."""
    out = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        for hour in SHIFT_STARTS:
            b = day.replace(hour=hour)
            if start < b < end:
                out.append(b)
        day += dt.timedelta(days=1)
    return out


class Roster:
    """Who is present when. Each operator pool always keeps at least one operator; support staff may be absent or half-day."""

    def __init__(self, start_date: dt.date, days: int, seed: int):
        rng = random.Random(seed * 7 + 1)
        self._status: dict[tuple[str, str, dt.date], str] = {}
        for d in range(days + 1):
            date = start_date + dt.timedelta(days=d)
            for shift, pool in OPERATORS.items():
                absent = rng.choice(pool) if len(pool) > 1 and rng.random() < 0.08 else None
                for worker in pool:
                    self._status[(worker, shift, date)] = "absent" if worker == absent else "present"
            for worker in SUPPORT:
                roll = rng.random()
                self._status[(worker, "A", date)] = "absent" if roll < 0.04 else "half_day" if roll < 0.09 else "present"

    def status(self, worker: str, shift: str, date: dt.date) -> str:
        return self._status.get((worker, shift, date), "absent")

    def present(self, shift: str, date: dt.date) -> list[str]:
        return [w for w in OPERATORS[shift] if self.status(w, shift, date) == "present"]

    def operator(self, machine: str, t: dt.datetime) -> str:
        shift, date = shift_of(t)
        pool = self.present(shift, date)
        return pool[MACHINE_INDEX[machine] % len(pool)]

    def sheet(self, shift: str, date: dt.date) -> dict[str, str]:
        workers = OPERATORS[shift] + (SUPPORT if shift == "A" else [])
        return {w: self.status(w, shift, date) for w in workers}


@dataclass(frozen=True)
class Event:
    t: dt.datetime
    seq: int
    action: str
    args: dict


@dataclass(frozen=True)
class OrderSpec:
    key: str
    buyer: str
    fabric: str
    colour: str
    metres: int
    price: int
    day: int                       # created on this day of the month, at 09:00
    deadline_days: int
    state: str = "confirmed"       # confirmed | draft | cancelled
    story: str = ""                # "" | bad | loss | late | no_yarn
    opening_lot: bool = False      # its yarn lot arrived 4 days before the month began
    hold: int = 0                  # hours the truck waits, loaded, before the driver signs it out (a truck still loading "now")


SHARMA, KAVYA = "Sharma Fabrics", "Kavya Garments"
ORDERS = [
    OrderSpec("O1", SHARMA, "Poplin 58in", "navy", 4000, 120, 0, 12, opening_lot=True),
    OrderSpec("O2", KAVYA, "Twill 58in", "charcoal", 3000, 150, 1, 12),
    OrderSpec("O3", SHARMA, "Poplin 58in", "white", 3500, 118, 3, 12),
    OrderSpec("O4", KAVYA, "Poplin 58in", "maroon", 2500, 110, 6, 12),
    OrderSpec("O5", SHARMA, "Twill 58in", "grey", 3000, 148, 7, 12),
    OrderSpec("O6", KAVYA, "Poplin 58in", "red", 2000, 48, 9, 12, story="loss"),      # under 5 rolls: its lot is never tested
    OrderSpec("O7", SHARMA, "Poplin 58in", "sky blue", 3000, 122, 11, 12, story="bad"),
    OrderSpec("O8", KAVYA, "Poplin 58in", "teal", 3000, 118, 12, 12, story="bad"),
    OrderSpec("O9", SHARMA, "Twill 58in", "olive", 3500, 150, 22, 12, hold=20),
    OrderSpec("O10", KAVYA, "Twill 58in", "black", 3000, 152, 25, 12),
    OrderSpec("O11", SHARMA, "Poplin 58in", "burgundy", 6000, 115, 26, 4, story="late"),
    OrderSpec("O12", KAVYA, "Poplin 58in", "beige", 3000, 118, 28, 10, story="no_yarn"),
    OrderSpec("O13", KAVYA, "Twill 58in", "brown", 2000, 150, 29, 10, state="draft"),
    OrderSpec("O14", SHARMA, "Poplin 58in", "cream", 2000, 118, 5, 10, state="cancelled"),
]


@dataclass
class Plan:
    events: list[Event]
    end: dt.datetime
    day0: dt.datetime
    roster: Roster
    notes: dict = field(default_factory=dict)


class Builder:
    def __init__(self, end: dt.datetime, seed: int, days: int):
        self.end = end
        self.days = days
        self.rng = random.Random(seed)
        self.day0 = (end - dt.timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
        # long: a late order's pipeline is planned well past `end` (those events are dropped, but each still names an operator)
        self.roster = Roster(self.day0.date() - dt.timedelta(days=5), days + 90, seed)
        self.events: list[Event] = []
        self.busy: list[tuple[str, dt.datetime, dt.datetime]] = []        # every booked run: machine, start, end
        self.trucks = 0

    def at(self, day: int, hour: float = 9) -> dt.datetime:
        return self.day0 + dt.timedelta(days=day, hours=hour)

    def ev(self, t: dt.datetime, action: str, **args) -> None:
        self.events.append(Event(t, len(self.events), action, args))

    def machine_run(self, machine: str, start: dt.datetime, length_h: float, *, order: str, kind: str, run_key: str | None = None,
                    input_key: str | None = None, issue: tuple[str, float] | None = None, output_kg: float | None = None,
                    rolls: list[tuple[float, int, str]] = (), load: list[str] = (), roll: str | None = None) -> dt.datetime:
        """One machine-run: start (or rework start), hand-over at every shift change, end. Returns the end moment."""
        end = start + hours(length_h)
        operator = self.roster.operator(machine, start)
        if kind == "rework":
            self.ev(start, "rework_start", roll=roll, machine=machine, operator=operator)
        else:
            self.ev(start, "start_run", order=order, machine=machine, operator=operator, input_key=input_key, run_key=run_key)
        if issue:
            self.ev(start + minutes(5), "issue_yarn", machine=machine, lot=issue[0], qty_kg=issue[1])
        if load:
            self.ev(start + minutes(2), "load_rolls", machine=machine, rolls=list(load))
        for offset, metres, key in rolls:
            self.ev(min(start + hours(offset), end - minutes(1)), "roll_off", machine=machine, roll=key, metres=metres)
        for b in boundaries(start, end):
            self.ev(b, "handover", machine=machine, operator=self.roster.operator(machine, b))
        self.ev(end, "end_run", machine=machine, run_key=None, output_kg=output_kg)
        self.busy.append((machine, start, end))
        return end

    def slot(self, machines: list[str], earliest: dt.datetime, length_h: float) -> tuple[str, dt.datetime]:
        """The machine and start time of the earliest gap, no earlier than `earliest`, that fits a run of `length_h` hours:
        each machine's booked runs are kept as intervals, so a job planned later can still use an idle gap earlier."""
        best: tuple[str, dt.datetime] | None = None
        for m in machines:
            start = earliest
            for s, e in sorted((s, e) for mm, s, e in self.busy if mm == m):
                if start + hours(length_h) <= s:
                    break
                start = max(start, e)
            if best is None or start < best[1]:
                best = (m, start)
        return best

    def qc_time(self, ready: dt.datetime, bump: int = 0) -> dt.datetime:
        """The inspector works 07:00 to 13:30: the first moment at least two hours after `ready`, spread by `bump` minutes."""
        t = ready + hours(2) + minutes(7 * bump)
        if t.hour < 7:
            t = t.replace(hour=7, minute=self.rng.randint(0, 40))
        elif t.hour > 13 or (t.hour == 13 and t.minute > 30):
            t = (t + dt.timedelta(days=1)).replace(hour=7, minute=self.rng.randint(0, 40))
        return t


def _need_kg(o: OrderSpec) -> float:
    per_m, waste, *_rest = RECIPE[o.fabric]
    return round(o.metres * per_m * (1 + waste) * 2) / 2


def _split_rolls(rng: random.Random, total: int) -> list[int]:
    lengths, left = [], total
    while left > 600:
        n = rng.randint(420, 600)
        lengths.append(n)
        left -= n
    if left < 150 and lengths:
        lengths[-1] += left
    else:
        lengths.append(left)
    return lengths


def _batch(b: Builder, o: OrderSpec, tag: str, metres_total: int, kg: float, lot: str, earliest: dt.datetime,
           kind: str) -> list[tuple[dt.datetime, str, str, int]]:
    """Spin, weave, dye and inspect `metres_total` of an order. Returns each roll's final result: (time, roll, verdict, metres).
    `tag` is empty for the order's first batch and ":r" for the replacement batch that re-makes rejected metres."""
    machine, start = b.slot(SPINNERS, earliest, kg / min(RATE[m] for m in SPINNERS) * 1.05)
    spin_end = b.machine_run(machine, start, kg / RATE[machine] * b.rng.uniform(0.97, 1.05), order=o.key, kind="spin",
                             run_key=f"spin:{o.key}{tag}", issue=(lot, kg), output_kg=kg)
    n_looms = 1 if metres_total < 600 else 3 if metres_total > 4000 else 2
    shares = [round(metres_total / n_looms)] * (n_looms - 1)
    shares.append(metres_total - sum(shares))
    longest = max(shares) / RATE[LOOMS[0]]
    looms = [m for _s, m in sorted((b.slot([m], spin_end, longest)[1], m) for m in LOOMS)[:n_looms]]
    rolls: list[tuple[str, int, dt.datetime, str]] = []         # key, metres, ready, producing operator
    weave_end = spin_end
    for loom, share in zip(looms, shares):
        wstart = b.slot([loom], spin_end, share / RATE[loom])[1]
        offset, plan_rolls = 0.0, []
        for i, metres in enumerate(_split_rolls(b.rng, share)):
            offset += metres / RATE[loom]
            plan_rolls.append((offset, metres, f"roll:{o.key}{tag}:{loom}:{i}"))
        end = b.machine_run(loom, wstart, share / RATE[loom], order=o.key, kind="weave", input_key=f"spin:{o.key}{tag}",
                            rolls=plan_rolls)
        weave_end = max(weave_end, end)
        for off, metres, key in plan_rolls:
            t = min(wstart + hours(off), end - minutes(1))
            rolls.append((key, metres, t, b.roster.operator(loom, t)))
    rolls.sort(key=lambda r: (r[2], r[0]))
    # dyeing, in two batches so both dyers work
    batches = [rolls[0::2], rolls[1::2]] if len(rolls) >= 4 else [rolls]
    ready_at: dict[str, dt.datetime] = {}
    for batch in batches:
        dyer, dstart = b.slot(DYERS, weave_end + minutes(30), sum(r[1] for r in batch) / RATE[DYERS[0]] * 1.05)
        dend = b.machine_run(dyer, dstart, sum(r[1] for r in batch) / RATE[dyer] * b.rng.uniform(0.97, 1.05), order=o.key,
                             kind="dye", load=[r[0] for r in batch])
        for r in batch:
            ready_at[r[0]] = dend
    # quality
    finals: list[tuple[dt.datetime, str, str, int]] = []
    for bump, (key, metres, _t, operator) in enumerate(rolls):
        odds = (0.78, 0.14, 0.08) if operator == UNLUCKY and kind == "normal" else ODDS[kind]
        verdict = b.rng.choices(["pass", "rework", "reject"], odds)[0]
        t1 = b.qc_time(ready_at[key], bump)
        defects = [] if verdict == "pass" else [(b.rng.choice(DEFECTS[kind]), b.rng.randint(1, 3))]
        b.ev(t1, "inspect", roll=key, verdict=verdict, defects=defects)
        if verdict != "rework":
            finals.append((t1, key, verdict, metres))
            continue
        if b.rng.random() < REDYE_SHARE[kind]:
            dyer, rstart = b.slot(DYERS, t1 + hours(3), metres / RATE[DYERS[0]] * 1.05)
            rend = b.machine_run(dyer, rstart, metres / RATE[dyer] * b.rng.uniform(0.97, 1.05), order=o.key, kind="rework", roll=key)
        else:
            rstart = (t1 + hours(3) + dt.timedelta(days=1)).replace(hour=7, minute=0)
            rend = rstart + hours(b.rng.uniform(2.5, 5.0))
            b.ev(rstart, "rework_start", roll=key, machine=None, operator=b.roster.present("A", rstart.date())[0])
            b.ev(rend, "end_run", machine=None, run_key=f"rework:{key}", output_kg=None)
        again = b.rng.choices(["pass", "reject"], AFTER_REWORK[kind])[0]
        t2 = b.qc_time(rend, bump)
        b.ev(t2, "inspect", roll=key, verdict=again, defects=[] if again == "pass" else [(b.rng.choice(DEFECTS[kind]), 1)])
        finals.append((t2, key, again, metres))
    return finals


def _plan_order(b: Builder, o: OrderSpec, state: dict) -> None:
    t0 = b.at(o.day, 9)
    b.ev(t0, "create_order", order=o.key, buyer=o.buyer, fabric=o.fabric, colour=o.colour, metres=o.metres, price=o.price,
         deadline_days=o.deadline_days)
    if o.state == "draft":
        return
    b.ev(t0 + minutes(10), "confirm_order", order=o.key)
    if o.state == "cancelled":
        b.ev(t0 + hours(30), "cancel_order", order=o.key)
        return
    per_m, waste, yarn, supplier, (lo, hi) = RECIPE[o.fabric]
    kg = _need_kg(o)
    if o.story == "no_yarn":
        return                                          # the yarn has not arrived: nothing can run, the shortage shows
    if o.story == "bad":
        lot = "lot:bad"
        if "bad_lot" not in state:                      # the first bad order brings the lot both bad orders draw from
            other = next(x for x in ORDERS if x.story == "bad" and x.key != o.key)
            b.ev(t0 + hours(3), "receive_lot", lot=lot, yarn=yarn, supplier=supplier,
                 qty_kg=math.ceil((kg + _need_kg(other)) * 1.05 / 10) * 10, cost_per_kg=250, order=None, challan=f"CH-BAD-{o.key}")
            state["bad_lot"] = True
    else:
        lot = f"lot:{o.key}"
        when = b.day0 - dt.timedelta(days=4) + hours(10) if o.opening_lot else t0 + hours(3)
        b.ev(when, "receive_lot", lot=lot, yarn=yarn, supplier=supplier, qty_kg=math.ceil(kg * 1.08 / 10) * 10,
             cost_per_kg=b.rng.randint(lo, hi), order=None if o.opening_lot else o.key, challan=f"CH-{o.key}")
    kind = o.story if o.story in ("bad", "loss") else "normal"
    finals = _batch(b, o, "", o.metres, kg, lot, t0 + hours(4), kind)
    # the mill re-makes what was rejected (an order is only complete when its good metres reach the ordered metres)
    rejected = sum(f[3] for f in finals if f[2] == "reject")
    if rejected:
        found = max(f[0] for f in finals if f[2] == "reject")
        redo_kg = round(rejected * per_m * (1 + waste) * 2) / 2
        b.ev(found + hours(2), "receive_lot", lot=f"lot:{o.key}:r", yarn=yarn, supplier=supplier,
             qty_kg=math.ceil(redo_kg * 1.08 / 10) * 10, cost_per_kg=b.rng.randint(lo, hi), order=o.key, challan=f"CH-{o.key}-R")
        finals += _batch(b, o, ":r", rejected, redo_kg, f"lot:{o.key}:r", found + hours(4), "remake")
    # trucks: the passed rolls, one truck (two for a big order), the morning after the last of them is ready
    passed = sorted((f for f in finals if f[2] == "pass"), key=lambda f: f[0])
    groups = [passed] if len(passed) < 8 else [passed[: len(passed) // 2], passed[len(passed) // 2:]]
    for group in groups:
        if not group:
            continue
        b.trucks += 1
        truck = f"truck:{b.trucks}"
        t = (group[-1][0] + dt.timedelta(days=1)).replace(hour=10, minute=0)
        b.ev(t, "dispatch_create", truck=truck, order=o.key, buyer=o.buyer, vehicle=f"KA-01-AB-{1000 + b.trucks}")
        for i, (_ft, key, _v, _m) in enumerate(group):
            b.ev(t + minutes(2 + 2 * i), "dispatch_scan", truck=truck, roll=key)
        done = t + minutes(10 + 2 * len(group)) + hours(o.hold)
        b.ev(done, "dispatch_confirm", truck=truck, order=o.key)
        state.setdefault("trucks", []).append((truck, o.key, done))


def _plan_money(b: Builder, state: dict) -> None:
    pays = [(truck, (done + dt.timedelta(days=b.rng.randint(7, 21))).replace(hour=11, minute=0))
            for truck, _order, done in state.get("trucks", [])]
    happening = sorted((p for p in pays if p[1] <= b.end), key=lambda p: p[1])
    partial = happening[2][0] if len(happening) > 2 else None   # the third payment of the month is only half
    for n, (truck, when) in enumerate(pays):
        b.ev(when, "buyer_payment", truck=truck, fraction=0.5 if truck == partial else 1.0, reference=f"NEFT-{7000 + n}")
    if b.days >= 30:
        for key in ("O2", "O3"):
            b.ev(b.at(14 if key == "O2" else 16, 11), "supplier_payment", lot=f"lot:{key}", fraction=1.0, reference=f"PAY-{key}")
        d0 = b.day0.date()
        b.ev(b.at(15, 18), "wage_period", start=d0, end=d0 + dt.timedelta(days=13), fraction=1.0)
        b.ev(b.at(29, 18), "wage_period", start=d0 + dt.timedelta(days=14), end=d0 + dt.timedelta(days=27), fraction=0.6)


def _plan_attendance(b: Builder) -> None:
    """Marked for every shift dated up to the end's own date, so the shifts still to come today are on the sheet too (the
    machines running "now" stay covered): a shift not yet started is marked at the end moment (an attendance row has no
    timestamp, and a date up to today is never "in the future" for the attendance rule)."""
    day = b.day0.date()
    while day <= b.end.date():
        for shift, hour in (("A", 6), ("B", 14), ("C", 22)):
            when = min(dt.datetime.combine(day, dt.time(hour), tzinfo=IST), b.end)
            b.ev(when, "attendance", date=day, shift=shift, entries=b.roster.sheet(shift, day))
        day += dt.timedelta(days=1)


def _plan_breakdowns(b: Builder) -> None:
    for machine, day, hour, length_h, reason in BREAKDOWNS:
        start = b.at(day, hour)
        while any(m == machine and s < start + hours(length_h) and e > start for m, s, e in b.busy):
            start += hours(6)
        b.ev(start, "breakdown", machine=machine, reason=reason)
        b.ev(start + hours(length_h), "repair", machine=machine)


def build_plan(end: dt.datetime, seed: int = 11, days: int = 30, orders: list[OrderSpec] | None = None) -> Plan:
    b = Builder(end, seed, days)
    state: dict = {}
    for o in sorted(orders if orders is not None else ORDERS, key=lambda x: (x.day, x.key)):
        _plan_order(b, o, state)
    _plan_money(b, state)
    _plan_attendance(b)
    if days >= 30:
        _plan_breakdowns(b)
    events = sorted((e for e in b.events if e.t <= end), key=lambda e: (e.t, e.seq))
    return Plan(events=events, end=end, day0=b.day0, roster=b.roster, notes={"trucks": state.get("trucks", [])})
