"""Spec §8.3, hand-worked: 100 inspected rolls, 12 defective, 14 groups tested."""
from fractions import Fraction as F

from app.modules.insights.engine.rootcause import RollFacts, analyse


def worked_mill():
    lots = [("L-15", 1), ("L-16", 1), ("L-17", 9), ("L-18", 1), ("L-19", 0)]           # five lots of 20 rolls
    rolls, n = [], 0
    for lot, bad in lots:
        for k in range(20):
            n += 1
            rolls.append((n, k < bad, lot))
    defective = [r[0] for r in rolls if r[1]]
    fine = [r[0] for r in rolls if not r[1]]
    loom05 = set(defective[:8]) | set(fine[:42])                                        # LOOM-05: 8 defective of 50
    return [RollFacts(n, bad, {
        "yarn_lot": [(lot, lot)],
        "weaving_machine": [("5", "LOOM-05")] if n in loom05 else [("4", "LOOM-04")],
        "weaving_operator": [(str(n % 4), f"Operator {n % 4}")],
        "weaving_shift": [(str(n % 3), "ABC"[n % 3])]}) for n, bad, lot in rolls]


def test_the_bad_lot_is_flagged_and_the_chance_pattern_is_not():
    rows = {(r.factor, r.value): r for r in analyse(worked_mill())}
    lot = rows[("yarn_lot", "L-17")]
    assert (lot.defective, lot.inspected, lot.rate, lot.rest_rate) == (9, 20, F(9, 20), F(3, 80))
    assert lot.p_value == F(277559, 20251032410) and lot.flagged
    operator = rows[("weaving_operator", "Operator 1")]
    assert (operator.defective, operator.inspected) == (6, 25) and float(operator.p_value) < 0.05 and not operator.flagged
    assert not rows[("weaving_machine", "LOOM-05")].flagged and float(rows[("weaving_machine", "LOOM-05")].p_value) > 0.17


def test_rows_are_sorted_by_p_value_and_only_groups_above_the_rest_are_listed():
    rows = analyse(worked_mill())
    assert [r.p_value for r in rows] == sorted(r.p_value for r in rows) and rows[0].value == "L-17"
    assert all(r.rate > r.rest_rate for r in rows)


def test_the_correction_counts_every_group_tested_not_just_the_ones_shown():
    rolls = worked_mill()
    assert len(analyse(rolls, max_rows=2)) == 2 and analyse(rolls, max_rows=2)[0].flagged
    only_lots = [RollFacts(r.roll_id, r.defective, {"yarn_lot": r.groups["yarn_lot"]}) for r in rolls]
    lot17 = next(r for r in analyse(only_lots) if r.value == "L-17")
    assert lot17.flagged                                                              # 5 tests: threshold 0.01, still far below


def test_a_group_under_five_inspected_rolls_is_not_tested():
    rolls = [RollFacts(i, i <= 3, {"yarn_lot": [("TINY", "TINY")] if i <= 4 else [("BIG", "BIG")]}) for i in range(1, 41)]
    assert [r.value for r in analyse(rolls)] == ["BIG"] or analyse(rolls) == []
    assert all(r.value != "TINY" for r in analyse(rolls))


def test_a_roll_in_two_lots_counts_in_both():
    rolls = [RollFacts(i, i <= 6, {"yarn_lot": [("L-1", "L-1"), ("L-2", "L-2")] if i <= 6 else [("L-3", "L-3")]})
             for i in range(1, 31)]
    values = {r.value for r in analyse(rolls)}
    assert {"L-1", "L-2"} <= values and "L-3" not in values                           # both lots carry the six defective rolls


def test_nothing_to_test_gives_no_rows():
    assert analyse([]) == []
    assert analyse([RollFacts(i, False, {"yarn_lot": [("L", "L")]}) for i in range(10)]) == []
