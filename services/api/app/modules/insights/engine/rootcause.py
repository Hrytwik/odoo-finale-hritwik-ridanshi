"""Spec §8.3: which machine, operator, shift or yarn lot has a defect rate too high to be chance?"""
from dataclasses import dataclass, field
from fractions import Fraction

from .fisher import fisher_greater

FACTORS = ("weaving_machine", "dyeing_machine", "weaving_operator", "weaving_shift", "yarn_lot")


@dataclass(frozen=True)
class RollFacts:
    roll_id: int
    defective: bool                                   # at least one inspector-confirmed defect, ever
    groups: dict[str, list[tuple[str, str]]] = field(default_factory=dict)   # factor -> [(key, label)]; a roll may have several lots


@dataclass(frozen=True)
class Row:
    factor: str
    value: str
    defective: int
    inspected: int
    rate: Fraction
    rest_rate: Fraction
    p_value: Fraction
    flagged: bool


def analyse(rolls: list[RollFacts], min_group: int = 5, alpha: Fraction = Fraction(5, 100),
            max_rows: int = 10) -> list[Row]:
    """Every group of at least `min_group` inspected rolls is compared with all the other inspected rolls using the
    one-sided exact test. Bonferroni: the significance level is divided by the number of groups tested."""
    total, total_defective = len(rolls), sum(r.defective for r in rolls)
    members: dict[tuple[str, str], tuple[str, set[int]]] = {}
    for roll in rolls:
        for factor, values in roll.groups.items():
            for key, label in values:
                members.setdefault((factor, key), (label, set()))[1].add(roll.roll_id)
    defective_ids = {r.roll_id for r in rolls if r.defective}
    tested = []
    for (factor, _), (label, ids) in members.items():
        inside, rest = len(ids), total - len(ids)
        if inside < min_group or rest == 0:
            continue
        hit = len(ids & defective_ids)
        rest_hit = total_defective - hit
        tested.append((factor, label, hit, inside, rest_hit, rest, fisher_greater(hit, inside - hit, rest_hit, rest - rest_hit)))
    threshold = alpha / len(tested) if tested else alpha
    rows = [Row(f, label, hit, inside, Fraction(hit, inside), Fraction(rest_hit, rest), p, p < threshold)
            for f, label, hit, inside, rest_hit, rest, p in tested if Fraction(hit, inside) > Fraction(rest_hit, rest)]
    rows.sort(key=lambda r: (r.p_value, FACTORS.index(r.factor), r.value))
    return rows[:max_rows]
