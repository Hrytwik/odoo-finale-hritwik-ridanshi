"""Spec §7.3: hand each run's cost to the rolls it touched, spread the order pool, move rejected rolls' cost onto good rolls."""
from dataclasses import dataclass, field
from fractions import Fraction

from .records import Roll, RollRun, Run
from .runs import RunCost

PARTS = ("yarn", "machine", "labour", "rework")


def _zero() -> dict[str, Fraction]:
    return {p: Fraction(0) for p in PARTS}


@dataclass
class RollResult:
    roll_id: int
    metres: Fraction
    rejected: bool
    parts: dict[str, Fraction]          # its own runs plus its share of the order pool (before any reject share)
    reject_share: Fraction = Fraction(0)

    @property
    def own_total(self) -> Fraction:
        return sum(self.parts.values(), Fraction(0))

    @property
    def total(self) -> Fraction:
        return self.own_total + self.reject_share

    @property
    def per_metre(self) -> Fraction:
        return self.total / self.metres


@dataclass
class OrderResult:
    parts: dict[str, Fraction] = field(default_factory=_zero)
    rolls: dict[int, RollResult] = field(default_factory=dict)
    reject_cost: Fraction = Fraction(0)
    good_metres: Fraction = Fraction(0)
    rejected_metres: Fraction = Fraction(0)

    @property
    def total(self) -> Fraction:
        return sum(self.parts.values(), Fraction(0))

    @property
    def cost_per_good_metre(self) -> Fraction | None:
        return self.total / self.good_metres if self.good_metres > 0 else None

    @property
    def unabsorbed(self) -> Fraction:
        """Cost that no good roll carries yet: everything, while the order has no non-rejected roll."""
        return self.total if self.good_metres == 0 else Fraction(0)


def _split(amounts: dict[str, Fraction], metres: dict[int, Fraction]) -> dict[int, dict[str, Fraction]]:
    whole = sum(metres.values(), Fraction(0))
    return {rid: {p: a * m / whole for p, a in amounts.items()} for rid, m in metres.items()}


def _add(into: dict[str, Fraction], amounts: dict[str, Fraction]) -> None:
    for part, amount in amounts.items():
        into[part] += amount


def allocate_order(runs: list[Run], rolls: list[Roll], roll_runs: list[RollRun],
                   costs: dict[int, RunCost]) -> OrderResult:
    """`runs`, `rolls` and `roll_runs` are all of ONE order. A run's yarn, machine and labour go to its rolls by
    metres (a rework run's whole cost is the 'rework' part); a run with no rolls goes into the pool, which is spread
    over all the order's rolls by metres. Then the rejected rolls' own totals are spread over the good rolls."""
    result = OrderResult()
    by_id = {r.id: r for r in rolls}
    result.rolls = {r.id: RollResult(r.id, r.metres, r.rejected, _zero()) for r in rolls}
    rolls_of_run: dict[int, dict[int, Fraction]] = {}
    for link in roll_runs:
        if link.roll_id in by_id:
            rolls_of_run.setdefault(link.run_id, {})[link.roll_id] = by_id[link.roll_id].metres
    pool = _zero()
    for run in runs:
        cost = costs[run.id]
        if run.stage == "rework":
            amounts = {**_zero(), "rework": cost.total}
        else:
            amounts = {**_zero(), "yarn": cost.yarn, "machine": cost.machine, "labour": cost.labour}
        _add(result.parts, amounts)
        own = rolls_of_run.get(run.id)
        if own:
            for rid, share in _split(amounts, own).items():
                _add(result.rolls[rid].parts, share)
        else:
            _add(pool, amounts)
    if rolls:
        for rid, share in _split(pool, {r.id: r.metres for r in rolls}).items():
            _add(result.rolls[rid].parts, share)
    good = {r.id: r.metres for r in rolls if not r.rejected}
    result.good_metres = sum(good.values(), Fraction(0))
    result.rejected_metres = sum((r.metres for r in rolls if r.rejected), Fraction(0))
    result.reject_cost = sum((result.rolls[r.id].own_total for r in rolls if r.rejected), Fraction(0))
    if good:
        for rid, share in _split({"x": result.reject_cost}, good).items():
            result.rolls[rid].reject_share = share["x"]
    return result


def is_final(runs: list[Run], rolls: list[Roll], good_metres: Fraction, ordered_metres: Fraction,
             cancelled: bool) -> bool:
    """No run open, every roll settled, and no more rolls coming (the ordered metres are woven, or the order is cancelled)."""
    return (all(r.end is not None for r in runs) and all(r.settled for r in rolls)
            and (cancelled or good_metres >= ordered_metres))
