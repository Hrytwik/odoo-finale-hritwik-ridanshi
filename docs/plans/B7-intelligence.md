# B7 — Intelligence (delivery dates, shortages, root causes, recall, buyer portal) Implementation Plan

> **Summary:** Replaces the example data behind `GET /orders/{code}/eta`, `/insights/late-orders`, `/insights/shortages`, `/insights/root-causes` and `/lots/{code}/recall` with real calculations (earliest-deadline-first delivery dates with what-ifs, a yarn reorder forecast, an exact Fisher test with Bonferroni correction for defect root causes, and the recall chain), fills in `delivery_date` and `days_late` on every order, and gives the buyer portal (built by Ridanshi on her branch, merged into main 2026-10-10 23:14 IST) its real delivery date. No contract change, no migration.
> **Last updated:** 2026-10-10 23:20 IST (Task 1 done and verified; Tasks 2-7 still to do)

> **How this plan is executed:** inline, one task at a time (atomic-workflow): test first, the full suite twice at each boundary, the important behaviours mutation-checked. Steps use checkbox (`- [ ]`) syntax.

**Goal:** the owner sees honest delivery dates, shortage warnings and defect suspects, the store can see where a recalled lot went, and a buyer can ask "will my order make the 20th?" and get the real answer.

**Architecture:** a pure engine package (`insights/engine/`: exact `fractions.Fraction` arithmetic, no database, no clock) takes plain records built by `insights/loader.py`; `insights/service.py` shapes the existing response models; the recall chain (`insights/recall.py`) is a plain read-only query. Nothing is stored, locked or published. The orders router fills in each order's dates from one whole-mill schedule.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL, pytest (`uv run python -m pytest -p no:warnings -o addopts=`). No new dependencies (the exact test replaces scipy).

**Spec:** `docs/specs/2026-10-10-textile-mill-design.md` §8 (the whole method, with hand-worked numbers) and §16. Read §8 first; this plan implements it exactly.

## Status

Written 2026-10-10 23:08 IST after the design was approved section by section (spec §8). **Verified before this plan was shown:** the four pure engines (`fisher`, `schedule`, `shortage`, `rootcause`) and their 40 tests were written and run in a scratch folder outside the repository (40 passed); the exact test agrees with `scipy.stats.fisher_exact` on 6,006 tables (worst relative difference 1.4e-15; scipy was installed only in a scratch environment); about twenty deliberate breaks of the engines were each caught by a test, after two weak tests were strengthened (a shift that does not change the date must not be offered; the 'harms' label); one of my own hand calculations was wrong and the engine was right (day 7 ends exactly at the level). **NOT run yet:** `loader.py`, `service.py`, the routes, `recall.py`, the portal, the settings and every API test (Tasks 4-6) have only been compile-checked; run them in the repository test-first (atomic-workflow step 3) and expect small fixes. Tasks 2-7 are still to do. **Update 23:15 IST:** Ridanshi's branch (portal backend and screens, 19 more assistant look-ups, auth sweep test) was merged into `main` (backend 1,264 passed twice, 3 skipped by design; web 527 passed; contract regenerates with no diff); her portal already does what Task 6 first planned except the delivery date, so Task 6 was rewritten to that one change. Baseline is now **1,264 passed**; the expected counts below already use it.

Task 1 done and verified (2026-10-10 23:20 IST): `insights/engine/{__init__,fisher,rootcause}.py` and 19 tests (13 for the exact test, including a brute-force enumeration of every arrangement on ten small tables and the 9-of-20 case at exactly 277559/20251032410; 6 for the root-cause engine, including the worked mill where lot L-17 is flagged and Operator 1 is not because of the correction); they failed first (collection error) then passed; the four planned mutations (wrong tail of the test, no Bonferroni correction, the five-roll minimum ignored, the above-the-rest filter removed) were each caught and the files restored; full suite 1,283 passed twice, 3 skipped (1,264 + 19). No route, database or contract change.

## Global Constraints

- Everything is **read-only**: no locks, no events, no migration, no new table. `contracts/` stays byte-identical (every shape already exists).
- Arithmetic in the engines is exact (`fractions.Fraction`); floats appear only in the JSON. Days are counted from today (`core.clock.today_ist()`); the engine never reads a clock.
- Roles are unchanged: late orders, ETA and root causes for owner, accountant, supervisor; shortages also for store; recall for store and owner; portal for buyers only.
- The portal (Ridanshi's `portal/service.py`) shows a buyer only their own confirmed or cancelled orders; a foreign order, a missing order and the buyer's own draft give the identical 404 (R15); its wording never names a machine, operator, lot, supplier or cost. Her seven tests in `tests/test_contract_portal.py` guard that; B7 does not change it.
- Settings (`app/config.py`, spec defaults): `QC_DAYS` 1, `DISPATCH_DAYS` 1, `DEFAULT_EFFICIENCY` 0.8, `EFFICIENCY_WINDOW_DAYS` 7, `EFFICIENCY_MIN_HOURS` 1, `STAGE_SHIFTS` empty, `ROOT_CAUSE_MIN_GROUP` 5, `ROOT_CAUSE_ALPHA` 0.05, `REORDER_ROUND_KG` 50.
- Tests that depend on dates are relative to today, except the portal timeline test which uses fixed October 2026 instants.
- The assistant's handlers keep their names (`late_orders`, `order_eta`, `shortages`, `root_causes`, `lot_recall`, `my_orders`, `my_order`) and take `db` (and `user` for the portal): the assistant calls them by name and passes those.
- Commit messages: plain imperative subject, no trailers. Never `git push`. Run the project's authorship scan on the staged diff before every commit.
- Live checks only on a throwaway database and port 8123, never against Hritwik's servers or database.

## Hand-worked numbers (the tests assert these)

**Delivery date** (engine, capacities per day: spinning 200 kg, weaving 100 m, dyeing 150 m; today 10 Oct): ORD-A (deadline 14 Oct; 100 kg, 300 m, 300 m left), ORD-B (25 Oct; 400, 200, 200), ORD-C (30 Oct; 0, 100, 100). ORD-A finishes at day 0.5 / 3 / 3, delivery 3 + 1 + 1 days = **15 Oct, 1 day late**, delay added 0.5 / 2.5 / 0, bottleneck **weaving**; ORD-B day 5, **17 Oct**; ORD-C day 6, **18 Oct**. Weaving at ×1.5: ORD-A **14 Oct, 0 late** (B and C 16 Oct). If ORD-B's deadline were 16 Oct: 1 day late; to the front: **14 Oct**, and ORD-A **17 Oct, 3 days late**. Capacity: two looms of 25 m/h, 2 shifts of 8 h, efficiency 0.8: 2 × 25 × 16 × 0.8 = **640 m/day**; 3 shifts **960**.

**Shortage** (engine, today 10 Oct): cotton 800 kg on hand, level 300, lead time 5 days; ORD-A 200 kg over 1 day, ORD-B 400 kg over 3 days: end-of-day stock 466.67, 333.33, 200 → falls below **12 Oct**, order by **7 Oct**, **3 days overdue**, free **200**, suggested **100 kg**. The contract's example (free −417.5, level 300) → **750 kg**, today, order by 5 Oct, 5 days overdue.

**Root cause** (engine): 100 inspected rolls, 12 defective, 14 groups tested, threshold 0.05 / 14 = **0.0036**: lot L-17 9 of 20 vs 3 of 80, p = **277559 / 20251032410 ≈ 0.0000137**, flagged; Operator 1 6 of 25 vs 8%, p 0.043, **not** flagged; LOOM-05 8 of 50 vs 8%, p 0.18.

**API delivery mill** (`tests/insights_world.py`, three 8-hour shifts, one machine per stage, efficiency at its 0.8 default; per day: spinning 25 × 0.8 × 24 = **480 kg**, weaving 12.5 × 0.8 × 24 = **240 m**, dyeing **480 m**; two untouched orders of 480 m needing 240 kg each; A due in 3 days, B in 10): A finishes spinning at day 0.5, weaving at 2, dyeing at 2 → delivery **today + 4**, **1 day late**, bottleneck weaving (stage dates +1, +2, +2); B finishes at day 1, 4, 4 → **today + 6**, on time. With `STAGE_SHIFTS=weaving=2` (160 m a day): A **today + 5**, 2 late; "Add a third shift on weaving" → **today + 4**, 1 late. **Shortage:** 100 kg on hand, level 50, supplier lead time 4 days, both orders draw 240 kg on day 1: free 100 − 480 = **−380**, below the level **today**, order by **today − 4**, **4 days overdue**, suggested 50 + 380 = 430 → **450 kg**. **Defect mill:** two groups of ten rolls (a lot, a loom, an operator and a shift each; group A alone is also dyed on one dye machine), six defective in group A, none in B: 6 of 10 vs 0 of 10, p = **1001 / 184756 ≈ 0.0054**; nine groups are tested, so the threshold is 0.05 / 9 = **0.00556** and group A's machine, dye machine, operator, shift and lot are all **flagged**. **Efficiency:** a finished order's weaving run of 5 hours that made 25 m on a loom rated 12.5 m/h gives efficiency 25 / 62.5 = **0.4**, so weaving makes 12.5 × 0.4 × 24 = **120 m a day**: order A's 480 m take 4 days, delivery **today + 6**, 3 days late; the same run ended ten days ago is outside the 7-day window and changes nothing.

**Recall mill:** lot L, 120 kg issued to S1, 50 kg issued to S2 and returned (net 0); S1's weaving run made R1 (dyeing), R2 and R3 (in store), R4 (dispatched, Sharma), R5 (on a loading truck, Kavya), R6 (rejected); S2's roll R7 is excluded. `on_floor` R1, R6; `in_store` R2, R3; `loading` R5; `dispatched` R4; Sharma 5 rolls, 1 dispatched; Kavya 1 roll, 0 dispatched, no truck codes.

**Portal:** Ridanshi's portal is already built and tested (timeline, trucks, `progress_pct` as a rough share: half weaving, a quarter dyeing, a quarter passed quality check, 100 once dispatched). B7 adds only the real delivery date: on the delivery mill, order A shows its buyer **today + 4 days** (deadline today + 3), the same date the staff screens show, and a cancelled order shows none.

## Review Focus (inputs the spec implies but no task would otherwise test)

1. **No machine working at a stage that has work, an empty mill, an order with no work left at a stage:** an unknown date, never a crash or a division by zero. Tasks 2 and 4.
2. **An order that is a draft, cancelled or already fully dispatched:** no date, `409 NOT_SCHEDULED` on the ETA route, not in the late list. Task 4.
3. **The portal's date and the staff date can disagree** (the portal reads the order service, which cannot see the schedule): one source for both, tested side by side. Task 6.
4. **A lot nobody used, an unknown lot, a lot that fed a roll that is later rejected:** an empty recall, a 404, a rejected roll shown on the floor. Task 5.
5. **Tiny samples and ties:** a group under five rolls is never tested; equal bottlenecks and equal deadlines break ties the same way every time. Tasks 1 and 2.

---

## File Structure

```
services/api/
  app/config.py                         + the nine settings and the STAGE_SHIFTS check
  app/modules/insights/
    engine/__init__.py                  the pure engines (docstring only)
    engine/fisher.py                    the exact one-sided Fisher test
    engine/rootcause.py                 groups, Bonferroni, rows
    engine/schedule.py                  capacity, efficiency, earliest-deadline-first queue, bottleneck, what-ifs
    engine/shortage.py                  the reorder forecast
    loader.py                           rows -> engine records
    service.py                          the schedule, ETA, late orders, shortages, root causes; order dates
    recall.py                           lot -> rolls -> buyers
    router.py                           the four real handlers (examples.py deleted)
  app/modules/store/router.py           the recall route calls insights.recall
  app/modules/orders/router.py          fills delivery_date and days_late
  app/modules/portal/service.py         (Ridanshi's) now takes the delivery date from insights; portal/examples.py deleted
  tests/
    test_insights_fisher.py             Task 1       test_insights_rootcause.py   Task 1
    test_insights_schedule.py           Task 2       test_insights_shortage.py    Task 3
    insights_world.py                   the hand-worked mills (Task 4; recall mill added in Task 5)
    test_insights_settings.py           Task 4       test_insights_api.py         Task 4
    test_recall_api.py                  Task 5       test_portal_dates.py         Task 6
docs: this plan, docs/plans/README.md, spec header, memory, the team note
```

**Dependency order:** Tasks 1, 2, 3 are independent pure code; Task 4 needs 1-3; Task 5 needs nothing earlier; Task 6 needs Task 4 (the delivery dates); Task 7 last.

**Run commands** (from the repository root): one file `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_insights_fisher.py -q`; the whole suite `cd services/api && uv run python -m pytest -p no:warnings -o addopts=`. Baseline before this work: **1,264 passed** (after merging Ridanshi's branch). This shell is zsh: an unquoted variable holding two paths is not split, so write file names out.

---

### Task 1: The exact test and the root-cause engine

**Files:**
- Create: `services/api/app/modules/insights/engine/__init__.py`, `fisher.py`, `rootcause.py`
- Test: create `services/api/tests/test_insights_fisher.py`, `tests/test_insights_rootcause.py`

**Interfaces:**
- Consumes: nothing (pure Python: `fractions`, `math`, `dataclasses`).
- Produces: `fisher.fisher_greater(a, b, c, d) -> Fraction` (a = defective in the group, b = fine in the group, c = defective elsewhere, d = fine elsewhere; raises `ValueError` on a negative count or an empty table); `rootcause.{FACTORS, RollFacts(roll_id, defective, groups: dict[factor, list[(key, label)]]), Row(factor, value, defective, inspected, rate, rest_rate, p_value, flagged), analyse(rolls, min_group=5, alpha=Fraction(5, 100), max_rows=10) -> list[Row]}`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_insights_fisher.py`:

```python
"""The exact one-sided test. Checked against known values and against an independent brute-force count."""
from fractions import Fraction as F
from itertools import combinations
from math import comb

import pytest
from app.modules.insights.engine.fisher import fisher_greater


def brute_force(a, b, c, d):
    """Pick the group's members out of everyone in every possible way and count the ways with at least `a` defective."""
    people = [True] * (a + c) + [False] * (b + d)             # True = defective
    group = a + b
    hits = sum(1 for chosen in combinations(range(len(people)), group) if sum(people[i] for i in chosen) >= a)
    return F(hits, comb(len(people), group))


def test_known_values():
    assert fisher_greater(9, 11, 3, 77) == F(277559, 20251032410)            # 9 of 20 defective vs 3 of 80 elsewhere
    assert fisher_greater(0, 5, 0, 5) == 1 and fisher_greater(5, 0, 5, 0) == 1
    assert fisher_greater(5, 0, 0, 5) == F(1, comb(10, 5))                   # all five defective in a group of five
    assert fisher_greater(1, 0, 0, 0) == 1


@pytest.mark.parametrize("table", [(2, 3, 1, 4), (3, 1, 2, 4), (0, 4, 4, 0), (4, 0, 0, 4), (1, 2, 3, 2), (2, 2, 2, 2),
                                   (3, 0, 1, 6), (5, 1, 0, 3), (1, 5, 3, 1), (2, 0, 2, 5)])
def test_it_agrees_with_counting_every_arrangement(table):
    assert fisher_greater(*table) == brute_force(*table)


def test_a_bigger_excess_is_always_less_likely_and_probabilities_stay_in_range():
    previous = F(1)
    for hit in range(0, 11):                                                  # 10 of a group of 20 defective in the best case
        p = fisher_greater(hit, 20 - hit, 10 - hit, 70 + hit)
        assert 0 < p <= previous <= 1
        previous = p


def test_bad_tables_are_refused():
    with pytest.raises(ValueError):
        fisher_greater(-1, 2, 3, 4)
    with pytest.raises(ValueError):
        fisher_greater(0, 0, 0, 0)
```

`services/api/tests/test_insights_rootcause.py`:

```python
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
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_insights_fisher.py tests/test_insights_rootcause.py -q`
Expected: collection errors, `ModuleNotFoundError: No module named 'app.modules.insights.engine'`.

- [ ] **Step 3: Write the engine**

`services/api/app/modules/insights/engine/__init__.py`:

```python
"""The insights engines: pure functions on plain records, with no database and no clock ("today" is always passed in).
All arithmetic is exact (fractions.Fraction); dates appear only at the very end."""
```

`services/api/app/modules/insights/engine/fisher.py`:

```python
"""Fisher's exact test, one-sided, with exact arithmetic (no scipy). The same number scipy.stats.fisher_exact gives
for alternative='greater', but as an exact fraction."""
from fractions import Fraction
from math import comb


def fisher_greater(a: int, b: int, c: int, d: int) -> Fraction:
    """The chance, if defects were spread evenly by luck alone, of seeing at least `a` defective rolls in a group.
    Table: a = defective in the group, b = fine in the group, c = defective elsewhere, d = fine elsewhere.
    This is the hypergeometric tail with the table's row and column totals held fixed."""
    if min(a, b, c, d) < 0:
        raise ValueError("counts cannot be negative")
    group, defective, total = a + b, a + c, a + b + c + d
    if total == 0:
        raise ValueError("an empty table")
    ways = comb(total, group)
    return sum(Fraction(comb(defective, x) * comb(total - defective, group - x), ways)
               for x in range(a, min(group, defective) + 1))
```

`services/api/app/modules/insights/engine/rootcause.py`:

```python
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
```

- [ ] **Step 4: Run them and watch them pass.** Expected: `19 passed` (13 fisher, 6 root cause).

- [ ] **Step 5: Mutation-check** (revert after each; a surviving mutation means a weak test):
  1. `fisher.py`: `range(a, min(group, defective) + 1)` → `range(a + 1, ...)`: 13 fisher tests fail.
  2. `rootcause.py`: `threshold = alpha / len(tested) if tested else alpha` → `threshold = alpha`: `test_the_bad_lot_is_flagged_and_the_chance_pattern_is_not` fails (Operator 1 would be flagged).
  3. `if inside < min_group or rest == 0:` → `if rest == 0:`: `test_a_group_under_five_inspected_rolls_is_not_tested` fails.
  4. Delete the trailing `if Fraction(hit, inside) > Fraction(rest_hit, rest)` filter: `test_rows_are_sorted_by_p_value_and_only_groups_above_the_rest_are_listed` fails.

- [ ] **Step 6: Full suite twice.** Expected both times: **1,283 passed** (1,264 + 19).

- [ ] **Step 7: Sync and commit.** Append a `Task 1 done and verified (<live date and time>): ...` line to this plan's Status section (counts, mutations), edit the `Last updated` header, then:

```bash
git add services/api/app/modules/insights/engine services/api/tests/test_insights_fisher.py services/api/tests/test_insights_rootcause.py docs/plans/B7-intelligence.md
git commit -m "Add the exact Fisher test and the defect root-cause engine"
```

---

### Task 2: The delivery-date engine

**Files:**
- Create: `services/api/app/modules/insights/engine/schedule.py`
- Test: `services/api/tests/test_insights_schedule.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (the `engine` package from Task 1).
- Produces: `schedule.{STAGES, OpenOrder(code, deadline, confirmed_at, work: dict[stage, Fraction], fully_passed=False), StageCapacity(rate_per_hour, shift_hours: tuple[Fraction, ...], shifts_run; .per_day(shifts=None), .can_add_shift), EffRun(stage, hours, rated, output), observed_efficiency(runs, default, min_hours) -> dict[stage, Fraction], queue_order(orders, front=None), Plan(finish, added, delivery), make_plan(orders, capacity: dict[stage, Fraction], today, qc_days=1, dispatch_days=1, front=None) -> Plan, WhatIf(kind, label, delivery, days_late), Eta(code, deadline, delivery, days_late, bottleneck, stage_dates, what_ifs), days_late(order, delivery), all_etas(orders, stages: dict[stage, StageCapacity], today, qc_days=1, dispatch_days=1, only=None, with_what_ifs=True) -> dict[code, Eta | None]}`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_insights_schedule.py`:

```python
"""Spec §8.1, hand-worked. Capacities per day: spinning 200 kg, weaving 100 m, dyeing 150 m; today is 10 Oct 2026."""
import datetime as dt
import random
from fractions import Fraction as F

import pytest
from app.modules.insights.engine.schedule import (
    EffRun, OpenOrder, StageCapacity, all_etas, make_plan, observed_efficiency, queue_order,
)

TODAY = dt.date(2026, 10, 10)
CONFIRMED = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
CAP = {"spinning": F(200), "weaving": F(100), "dyeing": F(150)}


def order(code, deadline_day, spin, weave, dye, passed=False, confirmed=CONFIRMED):
    return OpenOrder(code, dt.date(2026, 10, deadline_day), confirmed,
                     {"spinning": F(spin), "weaving": F(weave), "dyeing": F(dye)}, passed)


def trio(b_deadline=25):
    return [order("ORD-A", 14, 100, 300, 300), order("ORD-B", b_deadline, 400, 200, 200), order("ORD-C", 30, 0, 100, 100)]


def stages(weaving_shifts=2, weaving_per_day=100):
    """Three 8-hour shifts. Spinning (200 kg a day) and dyeing (150 m a day) run all three; weaving runs `weaving_shifts`
    of them and makes `weaving_per_day` metres a day at that setting."""
    shifts = (F(8), F(8), F(8))
    return {"spinning": StageCapacity(F(200, 24), shifts, 3),
            "weaving": StageCapacity(F(weaving_per_day, 8 * weaving_shifts), shifts, weaving_shifts),
            "dyeing": StageCapacity(F(150, 24), shifts, 3)}


def test_the_worked_case():
    plan = make_plan(trio(), CAP, TODAY)
    assert plan.finish["ORD-A"] == {"spinning": F(1, 2), "weaving": 3, "dyeing": 3}
    assert plan.added["ORD-A"] == {"spinning": F(1, 2), "weaving": F(5, 2), "dyeing": 0}
    assert plan.finish["ORD-B"] == {"spinning": F(5, 2), "weaving": 5, "dyeing": 5}
    assert plan.finish["ORD-C"] == {"spinning": 0, "weaving": 6, "dyeing": 6}              # no spinning left: passes straight through
    assert plan.delivery == {"ORD-A": dt.date(2026, 10, 15), "ORD-B": dt.date(2026, 10, 17), "ORD-C": dt.date(2026, 10, 18)}


def test_a_late_order_names_its_bottleneck_and_the_shift_that_would_fix_it():
    eta = all_etas(trio(), stages(weaving_shifts=2), TODAY)["ORD-A"]                        # weaving: 100 m a day on 2 of 3 shifts
    assert (eta.delivery, eta.days_late, eta.bottleneck) == (dt.date(2026, 10, 15), 1, "weaving")
    assert eta.stage_dates == {"spinning": dt.date(2026, 10, 11), "weaving": dt.date(2026, 10, 13), "dyeing": dt.date(2026, 10, 13)}
    assert [(w.kind, w.label, w.delivery, w.days_late) for w in eta.what_ifs] == [
        ("add_shift", "Add a third shift on weaving", dt.date(2026, 10, 14), 0)]       # already first, so no move-to-front


def test_moving_an_order_to_the_front_names_the_orders_it_harms():
    etas = all_etas(trio(b_deadline=16), stages(weaving_shifts=3), TODAY)
    b = etas["ORD-B"]
    assert (b.delivery, b.days_late, b.bottleneck) == (dt.date(2026, 10, 17), 1, "spinning")            # a tie, the earlier stage wins
    assert [(w.kind, w.delivery, w.days_late) for w in b.what_ifs] == [("move_to_front", dt.date(2026, 10, 14), 0)]
    assert b.what_ifs[0].label == "Move ORD-B to the front of every queue (ORD-A would be 3 days late)"


def test_an_on_time_order_has_no_bottleneck_and_no_what_ifs():
    eta = all_etas(trio(), stages(), TODAY)["ORD-B"]
    assert (eta.days_late, eta.bottleneck, eta.what_ifs) == (0, None, [])


def test_the_ordinal_labels_and_the_no_add_shift_when_every_shift_already_runs():
    full = stages(weaving_shifts=3)
    assert not full["weaving"].can_add_shift and stages(weaving_shifts=2)["weaving"].can_add_shift
    late = all_etas([order("ORD-A", 11, 100, 300, 300)], full, TODAY)["ORD-A"]
    assert late.days_late > 0 and all(w.kind != "add_shift" for w in late.what_ifs)


def test_the_qc_day_is_skipped_when_everything_has_passed():
    done = [order("ORD-P", 30, 0, 0, 0, passed=True), order("ORD-Q", 30, 0, 0, 0)]
    plan = make_plan(done, CAP, TODAY)
    assert (plan.delivery["ORD-P"], plan.delivery["ORD-Q"]) == (dt.date(2026, 10, 11), dt.date(2026, 10, 12))


def test_ties_go_to_the_earlier_confirmed_order_then_to_the_code():
    early = CONFIRMED
    late = CONFIRMED + dt.timedelta(days=1)
    queue = queue_order([order("ORD-9", 20, 1, 1, 1, confirmed=late), order("ORD-2", 20, 1, 1, 1, confirmed=late),
                         order("ORD-5", 20, 1, 1, 1, confirmed=early), order("ORD-1", 19, 1, 1, 1, confirmed=late)])
    assert [o.code for o in queue] == ["ORD-1", "ORD-5", "ORD-2", "ORD-9"]


def test_a_stage_with_work_and_no_capacity_makes_the_date_unknown_for_that_order_and_those_behind_it():
    no_loom = {**CAP, "weaving": F(0)}
    plan = make_plan(trio(), no_loom, TODAY)
    assert plan.delivery["ORD-A"] is None and plan.delivery["ORD-B"] is None and plan.delivery["ORD-C"] is None
    assert plan.finish["ORD-A"]["spinning"] == F(1, 2)                                  # earlier stages are still known
    ahead = [order("ORD-X", 12, 100, 0, 0), *trio()]
    assert make_plan(ahead, no_loom, TODAY).delivery["ORD-X"] is not None                  # nothing to weave: not stuck
    assert all_etas(trio(), {**stages(), "weaving": StageCapacity(F(0), (F(8),) * 3, 2)}, TODAY)["ORD-A"] is None   # a loom-less stage


def test_capacity_is_rated_output_times_efficiency_times_hours():
    loom = StageCapacity(F(2 * 25) * F(4, 5), (F(8), F(8), F(8)), 2)           # two looms of 25 m/h at 0.8
    assert loom.per_day() == 640 and loom.per_day(3) == 960 and loom.per_day(1) == 320


def test_observed_efficiency():
    runs = [EffRun("weaving", F(5), F(25), F(100)), EffRun("weaving", F(5), F(25), F(100))]
    assert observed_efficiency(runs)["weaving"] == F(4, 5)                                # 200 / 250
    assert observed_efficiency(runs)["spinning"] == F(4, 5)                               # no history: the default
    assert observed_efficiency([EffRun("weaving", F(5), F(25), F(500))])["weaving"] == 1  # capped at 1
    assert observed_efficiency([EffRun("weaving", F(1, 2), F(25), F(1))])["weaving"] == F(4, 5)   # under an hour: the default
    assert observed_efficiency([EffRun("weaving", F(3), F(25), F(0))])["weaving"] == 0    # a real, bad result stays bad


def test_property_more_capacity_never_delays_anyone_and_the_front_never_hurts_the_mover():
    rng = random.Random(8)
    for _ in range(300):
        orders = [OpenOrder(f"O{i}", dt.date(2026, 10, rng.randint(11, 30)), CONFIRMED + dt.timedelta(hours=i),
                            {"spinning": F(rng.randint(0, 500)), "weaving": F(rng.randint(0, 400)), "dyeing": F(rng.randint(0, 400))})
                  for i in range(rng.randint(1, 6))]
        cap = {"spinning": F(rng.randint(50, 300)), "weaving": F(rng.randint(30, 200)), "dyeing": F(rng.randint(30, 200))}
        base = make_plan(orders, cap, TODAY)
        faster = make_plan(orders, {k: v * F(3, 2) for k, v in cap.items()}, TODAY)
        for o in orders:
            assert faster.delivery[o.code] <= base.delivery[o.code]
            fin = base.finish[o.code]
            assert fin["spinning"] <= fin["weaving"] <= fin["dyeing"]                         # a stage never ends before the last
            assert make_plan(orders, cap, TODAY, front=o.code).delivery[o.code] <= base.delivery[o.code]


def test_a_what_if_that_does_not_change_the_date_is_not_offered():
    """100 m to weave at 100 m a day is exactly one day; with a third shift (150 m a day) it is two thirds of a day, which
    rounds up to the same one day, so adding a shift would not help and must not be suggested."""
    only = [order("ORD-A", 12, 0, 100, 0)]
    eta = all_etas(only, stages(weaving_shifts=2), TODAY)["ORD-A"]
    assert (eta.delivery, eta.days_late, eta.bottleneck) == (dt.date(2026, 10, 13), 1, "weaving")
    assert eta.what_ifs == []


def test_what_ifs_can_be_left_out_or_limited_to_one_order():
    cheap = all_etas(trio(b_deadline=16), stages(weaving_shifts=3), TODAY, with_what_ifs=False)
    assert cheap["ORD-B"].days_late == 1 and cheap["ORD-B"].what_ifs == []
    one = all_etas(trio(b_deadline=14), stages(weaving_shifts=2), TODAY, only="ORD-B")
    assert one["ORD-A"].days_late == 1 and one["ORD-A"].what_ifs == []                      # late too, but not asked about
    assert one["ORD-B"].days_late == 3 and [w.kind for w in one["ORD-B"].what_ifs] == ["move_to_front"]
```

- [ ] **Step 2: Run and watch them fail** (`ModuleNotFoundError: ...engine.schedule`).

Run: `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_insights_schedule.py -q`

- [ ] **Step 3: Write `schedule.py`**

`services/api/app/modules/insights/engine/schedule.py`:

```python
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
```

- [ ] **Step 4: Run and watch them pass.** Expected: `13 passed`.

- [ ] **Step 5: Mutation-check** (`schedule.py`; revert after each):
  1. Remove the `if work == 0:` pass-through (make the condition `False`): `test_the_worked_case` and the property test fail.
  2. `extra = dispatch_days + (0 if order.fully_passed else qc_days)` → always add `qc_days`: `test_the_qc_day_is_skipped_when_everything_has_passed` fails.
  3. Sort the queue by code instead of `(deadline, confirmed_at, code)`: `test_ties_go_to_the_earlier_confirmed_order_then_to_the_code` fails.
  4. `key=lambda s: (added[s], -STAGES.index(s))` → `(added[s], STAGES.index(s))`: the tie test (`ORD-B`, bottleneck spinning) fails.
  5. Change either `< delivery` improvement test to `<= delivery`: `test_a_what_if_that_does_not_change_the_date_is_not_offered` fails for the add-shift one, the worked-case what-if tests for the move-to-front one.
  6. Make `_harm` return an empty string: `test_moving_an_order_to_the_front_names_the_orders_it_harms` fails.
  7. Remove the cap `min(Fraction(1), ...)` in `observed_efficiency`, then the `hours < min_hours` default: `test_observed_efficiency` fails each time.

- [ ] **Step 6: Full suite twice.** Expected both times: **1,296 passed** (1,283 + 13).

- [ ] **Step 7: Sync and commit** (Status line, header, then):

```bash
git add services/api/app/modules/insights/engine/schedule.py services/api/tests/test_insights_schedule.py docs/plans/B7-intelligence.md
git commit -m "Add the delivery-date engine: queues, bottleneck and what-ifs"
```

---

### Task 3: The shortage engine

**Files:**
- Create: `services/api/app/modules/insights/engine/shortage.py`
- Test: `services/api/tests/test_insights_shortage.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `shortage.{Demand(order_code, outstanding_kg, window_days), Forecast(free_kg, falls_below_on, order_by, suggested_kg, overdue_days), spinning_window(finish_days: Fraction | None) -> int, round_up(kg, step) -> Fraction, forecast(on_hand_kg, reorder_level_kg, demands, lead_time_days: int | None, today, round_kg=50) -> Forecast | None}`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_insights_shortage.py`:

```python
"""Spec §8.2, hand-worked (today is 10 Oct 2026)."""
import datetime as dt
from fractions import Fraction as F

from app.modules.insights.engine.shortage import Demand, forecast, round_up, spinning_window

TODAY = dt.date(2026, 10, 10)


def test_the_worked_case_cotton_falls_below_on_the_12th():
    demands = [Demand("ORD-A", F(200), spinning_window(F(1, 2))), Demand("ORD-B", F(400), spinning_window(F(5, 2)))]
    assert [d.window_days for d in demands] == [1, 3]
    result = forecast(F(800), F(300), demands, 5, TODAY)          # stock at the end of each day: 466.67, 333.33, 200
    assert (result.free_kg, result.falls_below_on, result.order_by, result.overdue_days) == (
        200, dt.date(2026, 10, 12), dt.date(2026, 10, 7), 3)
    assert result.suggested_kg == 100


def test_the_contracts_own_example_suggests_750():
    result = forecast(F(100), F(300), [Demand("X", F("517.5"), 1)], 5, TODAY)
    assert (result.free_kg, result.suggested_kg) == (F(-835, 2), 750)
    assert (result.falls_below_on, result.order_by, result.overdue_days) == (TODAY, dt.date(2026, 10, 5), 5)


def test_a_type_that_never_falls_short_is_not_reported():
    assert forecast(F(800), F(300), [Demand("A", F(100), 2)], 5, TODAY) is None
    assert forecast(F(800), F(300), [], 5, TODAY) is None
    assert forecast(F(300), F(300), [], 5, TODAY) is None                          # exactly at the level is not below it


def test_already_below_the_level_means_today_even_with_no_orders():
    result = forecast(F(100), F(300), [], 5, TODAY)
    assert (result.falls_below_on, result.suggested_kg, result.order_by) == (TODAY, 200, dt.date(2026, 10, 5))


def test_no_supplier_means_no_order_by_date():
    result = forecast(F(100), F(300), [], None, TODAY)
    assert (result.order_by, result.overdue_days, result.falls_below_on) == (None, 0, TODAY)


def test_an_order_by_date_in_the_future_is_not_overdue():
    result = forecast(F(1000), F(300), [Demand("A", F(800), 8)], 2, TODAY)         # 100 kg a day: 900, 800, ... 300 on day 7
    assert result.falls_below_on == dt.date(2026, 10, 17)                          # day 7 ends AT 300 (not below), day 8 at 200
    assert result.order_by == dt.date(2026, 10, 15) and result.overdue_days == 0


def test_windows_and_rounding():
    assert spinning_window(F(0)) == 1 and spinning_window(F(1)) == 1 and spinning_window(F(11, 10)) == 2
    assert spinning_window(None) == 1                                              # cannot spin: all at once
    assert [round_up(F(x), 50) for x in (0, 1, 50, 51, 100, 717.5)] == [0, 50, 50, 100, 100, 750]


def test_stock_only_goes_down_so_it_is_reported_exactly_when_free_is_below_the_level():
    import random
    rng = random.Random(3)
    for _ in range(300):
        demands = [Demand(f"O{i}", F(rng.randint(0, 600)), rng.randint(1, 6)) for i in range(rng.randint(0, 4))]
        on_hand, level = F(rng.randint(0, 1500)), F(rng.randint(0, 500))
        result = forecast(on_hand, level, demands, 3, TODAY)
        free = on_hand - sum((d.outstanding_kg for d in demands), F(0))
        assert (result is not None) == (free < level)
        if result is not None:
            assert result.falls_below_on is not None and result.suggested_kg >= level - free
```

- [ ] **Step 2: Run and watch them fail.** `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_insights_shortage.py -q` → `ModuleNotFoundError: ...engine.shortage`.

- [ ] **Step 3: Write `shortage.py`**

`services/api/app/modules/insights/engine/shortage.py`:

```python
"""Spec §8.2: when does a yarn type fall below its reorder level, and when must the next order be placed?"""
import datetime as dt
import math
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Demand:
    order_code: str
    outstanding_kg: Fraction     # yarn this order still has to draw from stock
    window_days: int             # the days over which that draw is spread (its spinning window, at least 1)


@dataclass(frozen=True)
class Forecast:
    free_kg: Fraction
    falls_below_on: dt.date | None
    order_by: dt.date | None
    suggested_kg: Fraction
    overdue_days: int


def spinning_window(finish_days: Fraction | None) -> int:
    """Whole days from today to the end of an order's spinning, at least one. No spinning capacity: draw it all at once."""
    return 1 if finish_days is None else max(1, math.ceil(finish_days))


def round_up(kg: Fraction, step: int) -> Fraction:
    return Fraction(math.ceil(kg / step) * step)


def forecast(on_hand_kg: Fraction, reorder_level_kg: Fraction, demands: list[Demand], lead_time_days: int | None,
             today: dt.date, round_kg: int = 50) -> Forecast | None:
    """None when the yarn never falls below its reorder level. Stock only goes down (each order draws its outstanding
    yarn evenly over its window), so it ends at on_hand - total outstanding = free_kg; the day-by-day walk finds WHEN."""
    outstanding = sum((d.outstanding_kg for d in demands), Fraction(0))
    free = on_hand_kg - outstanding
    if free >= reorder_level_kg:
        return None
    falls = today if on_hand_kg < reorder_level_kg else None
    for day in range(1, max((d.window_days for d in demands), default=0) + 1):
        if falls is not None:
            break
        stock = on_hand_kg - sum(d.outstanding_kg * min(day, d.window_days) / d.window_days for d in demands)
        if stock < reorder_level_kg:
            falls = today + dt.timedelta(days=day - 1)        # it happens during that day
    order_by = None if lead_time_days is None or falls is None else falls - dt.timedelta(days=lead_time_days)
    return Forecast(free, falls, order_by, round_up(reorder_level_kg - free, round_kg),
                    max(0, (today - order_by).days) if order_by else 0)
```

- [ ] **Step 4: Run and watch them pass.** Expected: `8 passed`.

- [ ] **Step 5: Mutation-check** (revert after each):
  1. `if stock < reorder_level_kg:` → `<=`: `test_an_order_by_date_in_the_future_is_not_overdue` fails (day 7 ends exactly at the level).
  2. `falls - dt.timedelta(days=lead_time_days)` → `falls`: four tests fail.
  3. Round down instead of up in `round_up`: the worked case and the contract example fail.
  4. In `forecast`, return `None` when `free >= reorder_level_kg` → when `free > reorder_level_kg`: the "exactly at the level is not below it" assertion in `test_a_type_that_never_falls_short_is_not_reported` fails.

- [ ] **Step 6: Full suite twice.** Expected both times: **1,304 passed** (1,296 + 8).

- [ ] **Step 7: Sync and commit** (Status line, header, then):

```bash
git add services/api/app/modules/insights/engine/shortage.py services/api/tests/test_insights_shortage.py docs/plans/B7-intelligence.md
git commit -m "Add the yarn shortage forecast engine"
```

---

### Task 4: The settings, the four insight routes, and real dates on orders

**Files:**
- Modify: `services/api/app/config.py`, `services/api/app/modules/insights/router.py`, `services/api/app/modules/orders/router.py`
- Create: `services/api/app/modules/insights/loader.py`, `services/api/app/modules/insights/service.py`
- Delete: `services/api/app/modules/insights/examples.py` (after `grep -rn "insights.examples\|insights import examples" services/api` shows nothing else imports it)
- Test: create `services/api/tests/insights_world.py`, `tests/test_insights_settings.py`, `tests/test_insights_api.py`; update any older test that read the example insights, ETA or order dates (`grep -rn "late-orders\|/eta\|shortages\|root-causes\|delivery_date\|days_late" services/api/tests | grep -v test_insights`)

**Interfaces:**
- Consumes (Tasks 1-3): `engine.schedule.{STAGES, OpenOrder, StageCapacity, EffRun, observed_efficiency, all_etas, Eta}`, `engine.shortage.{Demand, forecast, spinning_window}`, `engine.rootcause.{RollFacts, analyse}`; existing `orders.service.{progress_row, get_order_or_404}`, `floor.service.db_now`, `core.clock.{today_ist, IST}`, `store.schemas.YarnTypeRef`, the views `v_yarn_type_stock`, `v_order_yarn_need`, `v_roll_latest_dye`.
- Produces: `loader.{load_open_orders(db) -> list[(Order, OpenOrder)], load_stages(db, now) -> dict[stage, StageCapacity], load_yarn(db) -> list[YarnInput], load_roll_facts(db) -> list[RollFacts], stage_shift_counts(), shift_length(shift)}`; `service.{Schedule(db, only=None, with_what_ifs=True), delivery_dates(db) -> dict[code, (date, days_late)], order_eta(db, code) -> EtaOut, late_orders(db), shortages(db), root_causes(db)}`. Error codes: `NOT_SCHEDULED` (409), `NO_CAPACITY` (409).

- [ ] **Step 1: Write the test mills and the failing tests**

`services/api/tests/insights_world.py` (the recall mill is added in Task 5):

```python
"""Small mills with every figure worked out by hand (docs/plans/B7-intelligence.md, 'Hand-worked numbers').
Dates are relative to today, because the delivery-date schedule counts days from today."""
import datetime as dt
from dataclasses import dataclass, field

from app.core.clock import today_ist
from app.db.models import QcDefect, YarnMovement
from tests.factories import (
    dye, make_buyer, make_dispatch, make_fabric_type, make_inspection, make_lot, make_machine, make_order, make_roll,
    make_run, make_shift, make_supplier, make_user, make_worker, make_yarn_type, put_on_dispatch,
)

LONG_AGO = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


@dataclass
class Mill:
    today: dt.date
    cotton: object
    supplier: object
    buyer: object
    fabric: object
    order_a: object            # 480 m, due in 3 days
    order_b: object            # 480 m, due in 10 days
    machines: dict = field(default_factory=dict)
    lot: object = None


def build_mill(db) -> Mill:
    """Three 8-hour shifts, one machine per stage, efficiency at its 0.8 default (no run has ended), so per day:
    spinning 25 x 0.8 x 24 = 480 kg, weaving 12.5 x 0.8 x 24 = 240 m, dyeing 25 x 0.8 x 24 = 480 m. Two untouched orders of 480 m
    (fabric 0.5 kg a metre, no wastage: 240 kg of yarn each)."""
    today = today_ist()
    for name, start, end in (("A", 6, 14), ("B", 14, 22), ("C", 22, 6)):
        make_shift(db, name=name, start_time=dt.time(start), end_time=dt.time(end))
    machines = {stage: make_machine(db, stage=stage, rated_output_per_hour=rated, running_cost_per_hour=0, created_at=LONG_AGO)
                for stage, rated in (("spinning", 25), ("weaving", 12.5), ("dyeing", 25))}
    cotton = make_yarn_type(db, reorder_level_kg=50)
    supplier = make_supplier(db, name="Vardhman Yarns", lead_time_days=4)
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.5, wastage_pct=0)
    buyer = make_buyer(db, name="Sharma Fabrics")
    a = make_order(db, buyer=buyer, fabric_type=fabric, qty_metres=480, deadline=today + dt.timedelta(days=3),
                   confirmed_at=dt.datetime(2026, 10, 1, tzinfo=dt.UTC))
    b = make_order(db, buyer=buyer, fabric_type=fabric, qty_metres=480, deadline=today + dt.timedelta(days=10),
                   confirmed_at=dt.datetime(2026, 10, 2, tzinfo=dt.UTC))
    lot = make_lot(db, yarn_type=cotton, supplier=supplier, qty_kg=100)
    return Mill(today, cotton, supplier, buyer, fabric, a, b, machines, lot)


@dataclass
class DefectMill:
    lot_a: object
    lot_b: object
    loom_a: object
    loom_b: object
    operator_a: object
    dyer: object


def build_defect_mill(db) -> DefectMill:
    """Twenty inspected rolls in two groups of ten that line up with a lot, a loom, an operator and a shift each; group A
    (alone) is also dyed on one dye machine. Six rolls from group A have a confirmed defect, none from group B: 6 of 10
    against 0 of 10, p = 1001 / 184756. Nine groups are big enough to test (two lots, two looms, two operators, two shifts,
    one dye machine), so the flag threshold is 0.05 / 9 = 0.00556 and all five of group A's factors are flagged."""
    order = make_order(db)
    make_shift(db, name="Day", start_time=dt.time(6), end_time=dt.time(22))
    make_shift(db, name="Night", start_time=dt.time(22), end_time=dt.time(6))
    dyer = make_machine(db, stage="dyeing")
    cotton = make_yarn_type(db)
    lots, looms, operators = [], [], []
    inspector = make_worker(db, role="inspector").id
    for _ in range(2):
        lot = make_lot(db, yarn_type=cotton, qty_kg=500)
        spin = make_run(db, order, make_machine(db, stage="spinning"), started_at=LONG_AGO, ended_at=LONG_AGO)
        db.add(YarnMovement(yarn_lot_id=lot.id, kind="issue", qty_kg=-100, production_run_id=spin.id,
                            moved_by=make_user(db).id))
        loom, operator = make_machine(db, stage="weaving"), make_worker(db, name=f"Operator {len(lots) + 1}")
        dye_run = make_run(db, order, dyer, started_at=LONG_AGO, ended_at=LONG_AGO) if not lots else None
        # group A starts at 05:30 IST (the night shift), group B eight hours later (the day shift)
        weave = make_run(db, order, loom, operator, input_run_id=spin.id, started_at=LONG_AGO + dt.timedelta(hours=8 * len(lots)))
        lots.append(lot)
        looms.append(loom)
        operators.append(operator)
        for n in range(10):
            roll = make_roll(db, order, weave, 100)
            bad = len(lots) == 1 and n < 6
            inspection = make_inspection(db, roll, "rework" if bad else "pass", inspector_worker_id=inspector)
            if bad:
                db.add(QcDefect(inspection_id=inspection.id, defect_type="hole", count=1))
            if len(lots) == 1:
                dye(db, roll, dye_run)
    db.flush()
    return DefectMill(lots[0], lots[1], looms[0], looms[1], operators[0], dyer)
```

`services/api/tests/test_insights_settings.py`:

```python
"""The intelligence settings: the spec's defaults, and a bad STAGE_SHIFTS fails loudly when the app starts."""
import pytest
from app.config import Settings
from pydantic import ValidationError


def test_the_defaults_are_the_specs():
    s = Settings(_env_file=None)
    assert (s.qc_days, s.dispatch_days, s.default_efficiency, s.efficiency_window_days, s.efficiency_min_hours) == (1, 1, 0.8, 7, 1)
    assert (s.stage_shifts, s.root_cause_min_group, s.root_cause_alpha, s.reorder_round_kg) == ("", 5, 0.05, 50)


@pytest.mark.parametrize("text", ["weaving=2", "weaving=2,dyeing=1", " spinning = 3 ", "", "weaving=2,"])
def test_good_stage_shifts_are_accepted(text):
    assert Settings(_env_file=None, stage_shifts=text).stage_shifts == text


@pytest.mark.parametrize("text", ["weaving", "weaving=", "weaving=two", "weaving=0", "weaving=-1", "knitting=2", "weaving=2;dyeing=1"])
def test_bad_stage_shifts_are_refused(text):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, stage_shifts=text)
```

`services/api/tests/test_insights_api.py`:

```python
"""B7: the delivery date, late orders, shortages and root causes through the API, on hand-worked mills
(tests/insights_world.py). Dates are relative to today."""
import datetime as dt

import pytest
from app.config import settings
from app.db.models import MachineDowntime, YarnMovement
from tests.factories import make_machine, make_order, make_roll, make_run
from tests.insights_world import build_defect_mill, build_mill

DAY = dt.timedelta(days=1)


@pytest.fixture
def mill(db):
    return build_mill(db)


def test_a_late_order_has_a_delivery_date_a_bottleneck_and_stage_dates(client, login_as, mill):
    login_as("owner")
    body = client.get(f"/api/orders/{mill.order_a.code}/eta").json()
    t = mill.today
    assert (body["delivery_date"], body["days_late"], body["bottleneck_stage"]) == (str(t + 4 * DAY), 1, "weaving")
    assert body["buyer_name"] == "Sharma Fabrics" and body["deadline"] == str(t + 3 * DAY)
    assert [(s["stage"], s["finish_date"]) for s in body["stages"]] == [
        ("spinning", str(t + DAY)), ("weaving", str(t + 2 * DAY)), ("dyeing", str(t + 2 * DAY))]
    assert body["what_ifs"] == []                                  # all three shifts already run; and A is already first


def test_an_order_on_time_has_no_bottleneck(client, login_as, mill):
    login_as("owner")
    body = client.get(f"/api/orders/{mill.order_b.code}/eta").json()
    assert (body["delivery_date"], body["days_late"], body["bottleneck_stage"], body["what_ifs"]) == (
        str(mill.today + 6 * DAY), 0, None, [])


def test_an_extra_shift_what_if_appears_when_weaving_runs_two_of_three_shifts(client, login_as, mill, monkeypatch):
    monkeypatch.setattr(settings, "stage_shifts", "weaving=2")
    login_as("owner")
    body = client.get(f"/api/orders/{mill.order_a.code}/eta").json()
    assert (body["delivery_date"], body["days_late"]) == (str(mill.today + 5 * DAY), 2)        # 480 m at 160 m a day
    assert body["what_ifs"] == [{"kind": "add_shift", "label": "Add a third shift on weaving",
                                 "delivery_date": str(mill.today + 4 * DAY), "days_late": 1}]


def test_late_orders_lists_only_the_late_ones(client, login_as, mill):
    login_as("owner")
    late = client.get("/api/insights/late-orders").json()
    assert [(o["order_code"], o["days_late"]) for o in late] == [(mill.order_a.code, 1)]


def test_the_order_list_and_detail_carry_the_real_dates(client, login_as, mill, db):
    draft = make_order(db, buyer=mill.buyer, fabric_type=mill.fabric, state="draft")
    login_as("owner")
    rows = {o["code"]: o for o in client.get("/api/orders").json()}
    assert (rows[mill.order_a.code]["delivery_date"], rows[mill.order_a.code]["days_late"]) == (str(mill.today + 4 * DAY), 1)
    assert (rows[mill.order_b.code]["delivery_date"], rows[mill.order_b.code]["days_late"]) == (str(mill.today + 6 * DAY), 0)
    assert (rows[draft.code]["delivery_date"], rows[draft.code]["days_late"]) == (None, None)       # not waiting for production
    one = client.get(f"/api/orders/{mill.order_a.code}").json()
    assert (one["delivery_date"], one["days_late"]) == (str(mill.today + 4 * DAY), 1)


def test_an_order_not_waiting_for_production_is_a_409(client, login_as, mill, db):
    draft = make_order(db, buyer=mill.buyer, fabric_type=mill.fabric, state="draft")
    login_as("owner")
    response = client.get(f"/api/orders/{draft.code}/eta")
    assert response.status_code == 409 and response.json()["code"] == "NOT_SCHEDULED"
    assert client.get("/api/orders/ORD-9999/eta").status_code == 404


def test_no_working_machine_at_a_stage_with_work_is_a_409_and_a_null_date(client, login_as, mill, db):
    db.add(MachineDowntime(machine_id=mill.machines["weaving"].id, reason="belt snapped"))
    db.flush()
    login_as("owner")
    response = client.get(f"/api/orders/{mill.order_a.code}/eta")
    assert response.status_code == 409 and response.json()["code"] == "NO_CAPACITY" and "weaving" in response.json()["message"]
    assert client.get(f"/api/orders/{mill.order_a.code}").json()["delivery_date"] is None
    assert client.get("/api/insights/late-orders").json() == []


def test_the_shortage_forecast_for_cotton(client, login_as, mill):
    """100 kg on hand, level 50, supplier lead time 4 days; both orders draw 240 kg within their first day:
    free = 100 - 480 = -380, below the level today, order by 4 days ago, 4 days overdue, suggest 50 + 380 = 430 -> 450 kg."""
    login_as("owner")
    rows = client.get("/api/insights/shortages").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["yarn_type"]["id"] == mill.cotton.id and row["supplier"] == {"id": mill.supplier.id, "name": "Vardhman Yarns"}
    assert (row["free_kg"], row["reorder_level_kg"], row["suggested_kg"], row["overdue_days"]) == (-380.0, 50.0, 450.0, 4)
    assert (row["falls_below_on"], row["order_by"]) == (str(mill.today), str(mill.today - 4 * DAY))


def test_a_blocked_lot_leaves_stock_and_raises_a_shortage_that_was_not_there(client, login_as, mill, db):
    db.add(YarnMovement(yarn_lot_id=mill.lot.id, kind="receipt", qty_kg=1000, moved_by=mill.lot.received_by))
    db.flush()                                                                         # 1,100 kg on hand covers the 480 kg needed
    login_as("owner")
    assert client.get("/api/insights/shortages").json() == []
    mill.lot.is_blocked = True
    db.flush()
    assert len(client.get("/api/insights/shortages").json()) == 1                      # a blocked lot is not stock


def test_root_causes_flag_the_group_that_is_unlikely_to_be_chance(client, login_as, db):
    world = build_defect_mill(db)
    login_as("supervisor")
    rows = client.get("/api/insights/root-causes").json()
    assert [(r["factor"], r["value"]) for r in rows] == [
        ("weaving_machine", world.loom_a.code), ("dyeing_machine", world.dyer.code), ("weaving_operator", "Operator 1"),
        ("weaving_shift", "Night"), ("yarn_lot", world.lot_a.lot_code)]
    for row in rows:
        assert (row["defective"], row["inspected"], row["rate"], row["rest_rate"], row["flagged"]) == (6, 10, 0.6, 0.0, True)
        assert row["p_value"] == pytest.approx(1001 / 184756)


def _recent_weaving_run(db, mill, ended_hours_ago, roll_metres):
    """A finished order whose weaving run took 5 hours and ended `ended_hours_ago` hours ago, making one roll."""
    done = make_order(db, state="cancelled")
    now = dt.datetime.now(dt.UTC)
    hours = dt.timedelta(hours=1)
    spin = make_run(db, done, mill.machines["spinning"], started_at=now - ended_hours_ago * hours - 6 * hours,
                    ended_at=now - ended_hours_ago * hours - 5 * hours)
    weave = make_run(db, done, mill.machines["weaving"], input_run_id=spin.id, started_at=now - ended_hours_ago * hours - 5 * hours,
                     ended_at=now - ended_hours_ago * hours)
    make_roll(db, done, weave, roll_metres)


def test_a_recent_slow_run_lowers_the_weaving_capacity(client, login_as, mill, db):
    """25 m in 5 hours on a loom rated 12.5 m/h is efficiency 25 / (12.5 x 5) = 0.4, so weaving makes 12.5 x 0.4 x 24 =
    120 m a day, not 240: order A's 480 m take 4 days, delivery today + 4 + 2, 3 days late."""
    _recent_weaving_run(db, mill, ended_hours_ago=1, roll_metres=25)
    login_as("owner")
    body = client.get(f"/api/orders/{mill.order_a.code}/eta").json()
    assert (body["delivery_date"], body["days_late"], body["bottleneck_stage"]) == (str(mill.today + 6 * DAY), 3, "weaving")


def test_a_run_that_ended_before_the_efficiency_window_is_ignored(client, login_as, mill, db):
    _recent_weaving_run(db, mill, ended_hours_ago=10 * 24, roll_metres=25)                      # ten days ago, window is seven
    login_as("owner")
    assert client.get(f"/api/orders/{mill.order_a.code}/eta").json()["delivery_date"] == str(mill.today + 4 * DAY)


def test_root_causes_are_empty_when_nothing_has_been_inspected(client, login_as, db):
    login_as("owner")
    assert client.get("/api/insights/root-causes").json() == []
    assert client.get("/api/insights/shortages").json() == []
    assert client.get("/api/insights/late-orders").json() == []


@pytest.mark.parametrize("role", ["store", "dispatch", "qc", "buyer"])
def test_planners_only(client, login_as, mill, role):
    login_as(role)
    for path in (f"/api/orders/{mill.order_a.code}/eta", "/api/insights/late-orders", "/api/insights/root-causes"):
        assert client.get(path).status_code == 403
    assert client.get("/api/insights/shortages").status_code == (200 if role == "store" else 403)
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_insights_settings.py tests/test_insights_api.py -q`
Expected: the settings tests fail (`Settings` has no such fields) and the API tests fail on the example figures.

- [ ] **Step 3: Add the settings.** Replace `services/api/app/config.py` with:

```python
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://localhost:5432/everest"
    test_database_url: str = "postgresql+psycopg://localhost:5432/everest_test"
    jwt_secret: str = "dev-only-secret-set-JWT_SECRET-in-env-file"
    jwt_ttl_hours: int = 12
    cookie_secure: bool = False
    upload_dir: str = "../../data/uploads"
    demo_data: bool = False
    llm_key_secret: str = ""

    # intelligence (spec 8): the spec's values are the defaults
    qc_days: int = 1                       # days a delivery date allows for quality check
    dispatch_days: int = 1                 # days it allows for dispatch
    default_efficiency: float = 0.8        # used while a stage has under efficiency_min_hours of recent run time
    efficiency_window_days: int = 7
    efficiency_min_hours: float = 1
    stage_shifts: str = ""                 # shifts run per stage, e.g. "weaving=2,dyeing=2"; a stage not listed runs all
    root_cause_min_group: int = 5
    root_cause_alpha: float = 0.05
    reorder_round_kg: int = 50

    @field_validator("stage_shifts")
    @classmethod
    def _check_stage_shifts(cls, value: str) -> str:
        for part in filter(None, (p.strip() for p in value.split(","))):
            stage, _, count = part.partition("=")
            if stage.strip() not in ("spinning", "weaving", "dyeing") or not count.strip().isdigit() or int(count) < 1:
                raise ValueError(f"STAGE_SHIFTS must look like weaving=2,dyeing=1 (stage=number of shifts); got {part!r}")
        return value


settings = Settings()
```

- [ ] **Step 4: Write the loader and the service.**

`services/api/app/modules/insights/loader.py`:

```python
"""Reads the rows the insights engines need and turns them into their plain records (no arithmetic happens here)."""
import datetime as dt
from dataclasses import dataclass
from fractions import Fraction

from sqlalchemy import column, func, select, table, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.clock import IST
from app.db.models import (
    Machine, MachineDowntime, Order, ProductionRun, QcDefect, QcInspection, Roll, RollRun, Shift, Worker, YarnLot,
    YarnMovement, YarnType,
)
from app.modules.insights.engine.rootcause import RollFacts
from app.modules.insights.engine.schedule import STAGES, EffRun, OpenOrder, StageCapacity, observed_efficiency
from app.modules.orders.service import progress_row

v_roll_latest_dye = table("v_roll_latest_dye", column("roll_id"), column("machine_id"))


def _frac(value) -> Fraction:
    return Fraction(value)


def _hours(delta: dt.timedelta) -> Fraction:
    return Fraction(delta.days * 86400 + delta.seconds, 3600)


def shift_length(shift: Shift) -> Fraction:
    """Hours in the shift; one whose end is not after its start runs into the next day."""
    span = dt.datetime.combine(dt.date.min, shift.end_time) - dt.datetime.combine(dt.date.min, shift.start_time)
    return _hours(span if span > dt.timedelta(0) else span + dt.timedelta(days=1))


def stage_shift_counts() -> dict[str, int]:
    """STAGE_SHIFTS such as 'weaving=2,dyeing=2' as {'weaving': 2, 'dyeing': 2} (validated when the settings load)."""
    out = {}
    for part in filter(None, (p.strip() for p in settings.stage_shifts.split(","))):
        stage, _, count = part.partition("=")
        out[stage.strip()] = int(count)
    return out


# ---- the delivery-date schedule ---------------------------------------------------------------------------------

def load_open_orders(db: Session) -> list[tuple[Order, OpenOrder]]:
    """Confirmed orders with metres still to dispatch, and what is left to do for each (spec 8.1)."""
    out = []
    for order in db.scalars(select(Order).where(Order.state == "confirmed").order_by(Order.id)):
        row = progress_row(db, order)
        if row["dispatched_m"] >= order.qty_metres:
            continue
        qty, woven, dyed = _frac(order.qty_metres), _frac(row["woven_m"]), _frac(row["dyed_m"])
        work = {"spinning": max(Fraction(0), _frac(row["need_kg"]) - _frac(row["spun_kg"])),
                "weaving": max(Fraction(0), qty - (woven - _frac(row["rejected_m"]))),
                "dyeing": max(Fraction(0), woven - dyed)}
        out.append((order, OpenOrder(order.code, order.deadline, order.confirmed_at, work,
                                     fully_passed=row["passed_m"] >= order.qty_metres)))
    return out


def _efficiency_runs(db: Session, now: dt.datetime) -> list[EffRun]:
    since = now - dt.timedelta(days=settings.efficiency_window_days)
    metres = dict(db.execute(
        select(RollRun.run_id, func.sum(Roll.metres)).join(Roll, Roll.id == RollRun.roll_id)
        .where(RollRun.purpose.in_(("produce", "dye"))).group_by(RollRun.run_id)).all())
    runs = []
    for run, rated in db.execute(
            select(ProductionRun, Machine.rated_output_per_hour).join(Machine, Machine.id == ProductionRun.machine_id)
            .where(ProductionRun.ended_at.is_not(None), ProductionRun.ended_at >= since, ProductionRun.ended_at <= now,
                   ProductionRun.stage.in_(STAGES))):
        if run.stage == "spinning":
            if run.output_kg is None:               # a run ended by hand-over keeps no output: it says nothing
                continue
            output = _frac(run.output_kg)
        else:
            output = _frac(metres.get(run.id, 0))
        runs.append(EffRun(run.stage, _hours(run.ended_at - run.started_at), _frac(rated), output))
    return runs


def load_stages(db: Session, now: dt.datetime) -> dict[str, StageCapacity]:
    """Per stage: rated output of the active machines that are up, times observed efficiency, and the shifts it runs."""
    shifts = tuple(shift_length(s) for s in db.scalars(select(Shift).order_by(Shift.id)))
    counts = stage_shift_counts()
    down = select(MachineDowntime.machine_id).where(MachineDowntime.ended_at.is_(None))
    machines = list(db.scalars(select(Machine).where(Machine.active.is_(True), Machine.id.not_in(down))))
    efficiency = observed_efficiency(_efficiency_runs(db, now), Fraction(str(settings.default_efficiency)),
                                     Fraction(str(settings.efficiency_min_hours)))
    return {stage: StageCapacity(
        sum((_frac(m.rated_output_per_hour) for m in machines if m.stage == stage), Fraction(0)) * efficiency[stage],
        shifts, min(counts.get(stage, len(shifts)), len(shifts))) for stage in STAGES}


# ---- the yarn shortage forecast ---------------------------------------------------------------------------------

@dataclass
class YarnInput:
    yarn_type: YarnType
    on_hand_kg: Fraction
    reorder_level_kg: Fraction
    supplier_id: int | None
    supplier_name: str | None
    lead_time_days: int | None
    demands: list[tuple[str, Fraction]]        # (order code, outstanding kg)


def load_yarn(db: Session) -> list[YarnInput]:
    stock = {r.yarn_type_id: r for r in db.execute(text(
        "SELECT yarn_type_id, on_hand_kg, reorder_level_kg FROM v_yarn_type_stock"))}
    demands: dict[int, list[tuple[str, Fraction]]] = {}
    for row in db.execute(text(
            "SELECT o.code, n.yarn_type_id, n.outstanding_kg FROM v_order_yarn_need n JOIN orders o ON o.id = n.order_id "
            "WHERE n.state = 'confirmed' AND n.outstanding_kg > 0")):
        demands.setdefault(row.yarn_type_id, []).append((row.code, _frac(row.outstanding_kg)))
    suppliers = {r.yarn_type_id: r for r in db.execute(text(
        "SELECT DISTINCT ON (l.yarn_type_id) l.yarn_type_id, s.id, s.name, s.lead_time_days "
        "FROM yarn_lots l JOIN suppliers s ON s.id = l.supplier_id "
        "ORDER BY l.yarn_type_id, l.received_at DESC, l.id DESC"))}
    out = []
    for yarn_type in db.scalars(select(YarnType).order_by(YarnType.code)):
        row, supplier = stock.get(yarn_type.id), suppliers.get(yarn_type.id)
        if row is None:
            continue
        out.append(YarnInput(yarn_type, _frac(row.on_hand_kg), _frac(row.reorder_level_kg),
                             supplier.id if supplier else None, supplier.name if supplier else None,
                             supplier.lead_time_days if supplier else None, demands.get(yarn_type.id, [])))
    return out


# ---- the defect root causes -------------------------------------------------------------------------------------

def _shift_name(started_at: dt.datetime, shifts: list[Shift]) -> str | None:
    moment = started_at.astimezone(IST).time()
    for shift in shifts:
        start, end = shift.start_time, shift.end_time
        if (start <= moment < end) if start < end else (moment >= start or moment < end):
            return shift.name
    return None


def load_roll_facts(db: Session) -> list[RollFacts]:
    """Every inspected roll with whether an inspector ever confirmed a defect on it, and the groups it belongs to."""
    inspected = set(db.scalars(select(QcInspection.roll_id).distinct()))
    defective = set(db.scalars(select(QcInspection.roll_id).join(QcDefect, QcDefect.inspection_id == QcInspection.id).distinct()))
    shifts = list(db.scalars(select(Shift).order_by(Shift.id)))
    made = {r.roll_id: r for r in db.execute(
        select(RollRun.roll_id, ProductionRun.input_run_id, ProductionRun.started_at, Machine.code.label("machine"),
               Worker.id.label("worker_id"), Worker.name.label("worker"))
        .join(ProductionRun, ProductionRun.id == RollRun.run_id).join(Machine, Machine.id == ProductionRun.machine_id)
        .join(Worker, Worker.id == ProductionRun.operator_worker_id)
        .where(RollRun.purpose == "produce", ProductionRun.stage == "weaving", RollRun.roll_id.in_(inspected or {0})))}
    dyers = dict(db.execute(select(v_roll_latest_dye.c.roll_id, Machine.code)
                            .join(Machine, Machine.id == v_roll_latest_dye.c.machine_id)
                            .where(v_roll_latest_dye.c.roll_id.in_(inspected or {0}))).all())
    spinning = {m.input_run_id for m in made.values() if m.input_run_id is not None}
    net = func.sum(YarnMovement.qty_kg)
    lots: dict[int, list[str]] = {}
    for run_id, lot_code in db.execute(
            select(YarnMovement.production_run_id, YarnLot.lot_code).join(YarnLot, YarnLot.id == YarnMovement.yarn_lot_id)
            .where(YarnMovement.production_run_id.in_(spinning or {0}), YarnMovement.kind.in_(("issue", "return")))
            .group_by(YarnMovement.production_run_id, YarnLot.lot_code).having(net < 0)):
        lots.setdefault(run_id, []).append(lot_code)
    facts = []
    for roll_id in sorted(inspected):
        groups: dict[str, list[tuple[str, str]]] = {}
        run = made.get(roll_id)
        if run is not None:
            groups["weaving_machine"] = [(run.machine, run.machine)]
            groups["weaving_operator"] = [(str(run.worker_id), run.worker)]
            shift = _shift_name(run.started_at, shifts)
            if shift is not None:
                groups["weaving_shift"] = [(shift, shift)]
            if run.input_run_id in lots:
                groups["yarn_lot"] = [(code, code) for code in sorted(lots[run.input_run_id])]
        if roll_id in dyers:
            groups["dyeing_machine"] = [(dyers[roll_id], dyers[roll_id])]
        facts.append(RollFacts(roll_id, roll_id in defective, groups))
    return facts
```

`services/api/app/modules/insights/service.py`:

```python
"""The insights on request (spec 8): load the rows, run the engines, shape the existing response models.
Nothing here writes, locks or publishes. Money-free: only dates, kilograms, metres and probabilities."""
import datetime as dt
from decimal import Decimal
from fractions import Fraction

from sqlalchemy.orm import Session

from app.config import settings
from app.core.clock import today_ist
from app.core.errors import AppError
from app.core.money import to_float
from app.core.schemas import Ref
from app.db.models import Order
from app.modules.floor.service import db_now
from app.modules.insights import loader
from app.modules.insights.engine.rootcause import analyse
from app.modules.insights.engine.schedule import STAGES, Eta, OpenOrder, StageCapacity, all_etas
from app.modules.insights.engine.shortage import Demand, forecast, spinning_window
from app.modules.insights.schemas import EtaOut, RootCauseRow, ShortageOut, StageFinish, WhatIf
from app.modules.orders.service import get_order_or_404
from app.modules.store.schemas import YarnTypeRef


class Schedule:
    """The whole mill's schedule, built once: an order's date depends on the orders ahead of it in every queue."""

    def __init__(self, db: Session, only: str | None = None, with_what_ifs: bool = True):
        self.today, now = today_ist(), db_now(db)
        pairs = loader.load_open_orders(db)
        self.orders: dict[str, OpenOrder] = {open_order.code: open_order for _, open_order in pairs}
        self.rows: dict[str, Order] = {order.code: order for order, _ in pairs}
        self.stages: dict[str, StageCapacity] = loader.load_stages(db, now)
        self.etas: dict[str, Eta | None] = all_etas(list(self.orders.values()), self.stages, self.today,
                                                    settings.qc_days, settings.dispatch_days, only, with_what_ifs)

    def missing_stage(self, code: str) -> str | None:
        """The first stage where this order has work and no machine is working."""
        order = self.orders[code]
        return next((s for s in STAGES if order.work[s] > 0 and self.stages[s].per_day() == 0), None)


def _eta_out(eta: Eta, order: Order) -> EtaOut:
    return EtaOut(
        order_code=eta.code, buyer_name=order.buyer.name, deadline=eta.deadline, delivery_date=eta.delivery,
        days_late=eta.days_late, bottleneck_stage=eta.bottleneck,
        stages=[StageFinish(stage=s, finish_date=eta.stage_dates[s]) for s in STAGES],
        what_ifs=[WhatIf(kind=w.kind, label=w.label, delivery_date=w.delivery, days_late=w.days_late) for w in eta.what_ifs])


def delivery_dates(db: Session) -> dict[str, tuple[dt.date, int]]:
    """order code -> (delivery date, days late) for every order waiting for production whose date is known."""
    schedule = Schedule(db, with_what_ifs=False)
    return {code: (eta.delivery, eta.days_late) for code, eta in schedule.etas.items() if eta is not None}


def order_eta(db: Session, order_code: str) -> EtaOut:
    order = get_order_or_404(db, order_code)
    schedule = Schedule(db, only=order_code)
    if order_code not in schedule.orders:
        raise AppError("NOT_SCHEDULED", "This order is not waiting for production", field="order_code", status=409)
    eta = schedule.etas[order_code]
    if eta is None:
        raise AppError("NO_CAPACITY", f"No working machine at {schedule.missing_stage(order_code)}",
                       field="order_code", status=409)
    return _eta_out(eta, order)


def late_orders(db: Session) -> list[EtaOut]:
    """Late orders, the most days late first."""
    schedule = Schedule(db)
    late = [(eta, schedule.rows[code]) for code, eta in schedule.etas.items() if eta is not None and eta.days_late > 0]
    late.sort(key=lambda pair: (-pair[0].days_late, pair[0].code))
    return [_eta_out(eta, order) for eta, order in late]


def shortages(db: Session) -> list[ShortageOut]:
    """Yarn types that are or will be below their reorder level, the most urgent first."""
    schedule = Schedule(db, with_what_ifs=False)
    rows = []
    for item in loader.load_yarn(db):
        demands = []
        for code, outstanding in item.demands:
            eta = schedule.etas.get(code)
            finish = None if eta is None else Fraction((eta.stage_dates["spinning"] - schedule.today).days)
            demands.append(Demand(code, outstanding, spinning_window(finish)))
        result = forecast(item.on_hand_kg, item.reorder_level_kg, demands, item.lead_time_days, schedule.today,
                          settings.reorder_round_kg)
        if result is None:
            continue
        yt = item.yarn_type
        rows.append(ShortageOut(
            yarn_type=YarnTypeRef(id=yt.id, code=yt.code, name=yt.name, colour=yt.colour),
            free_kg=to_float(_dec(result.free_kg)), reorder_level_kg=to_float(_dec(item.reorder_level_kg)),
            falls_below_on=result.falls_below_on,
            supplier=Ref(id=item.supplier_id, name=item.supplier_name) if item.supplier_id else None,
            order_by=result.order_by, suggested_kg=to_float(_dec(result.suggested_kg)), overdue_days=result.overdue_days))
    rows.sort(key=lambda r: (r.order_by is None, r.order_by or dt.date.max, r.yarn_type.code))
    return rows


def _dec(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def root_causes(db: Session) -> list[RootCauseRow]:
    rows = analyse(loader.load_roll_facts(db), settings.root_cause_min_group, Fraction(str(settings.root_cause_alpha)))
    return [RootCauseRow(factor=r.factor, value=r.value, defective=r.defective, inspected=r.inspected,
                         rate=float(r.rate), rest_rate=float(r.rest_rate), p_value=float(r.p_value), flagged=r.flagged)
            for r in rows]
```

- [ ] **Step 5: Serve the four routes for real.** Replace `services/api/app/modules/insights/router.py` with:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.modules.insights import schemas as s
from app.modules.insights import service

router = APIRouter(tags=["insights"])
planners = require_roles("owner", "accountant", "supervisor")
stock_planners = require_roles("owner", "accountant", "supervisor", "store")


@router.get("/insights/late-orders", response_model=list[s.EtaOut], dependencies=[Depends(planners)])
def late_orders(db: Session = Depends(get_db)) -> list[s.EtaOut]:
    return service.late_orders(db)


@router.get("/orders/{order_code}/eta", response_model=s.EtaOut, dependencies=[Depends(planners)])
def order_eta(order_code: str, db: Session = Depends(get_db)) -> s.EtaOut:
    return service.order_eta(db, order_code)


@router.get("/insights/shortages", response_model=list[s.ShortageOut], dependencies=[Depends(stock_planners)])
def shortages(db: Session = Depends(get_db)) -> list[s.ShortageOut]:
    return service.shortages(db)


@router.get("/insights/root-causes", response_model=list[s.RootCauseRow], dependencies=[Depends(planners)])
def root_causes(db: Session = Depends(get_db)) -> list[s.RootCauseRow]:
    return service.root_causes(db)
```

Then `git rm services/api/app/modules/insights/examples.py` once nothing imports it (the assistant reaches these handlers through `insights.router`, which keeps working).

- [ ] **Step 6: Fill in the order dates.** Replace `services/api/app/modules/orders/router.py` with (only `_dated` and the `return` lines changed):

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.modules.insights import service as insights
from app.modules.orders import schemas as s
from app.modules.orders import service

router = APIRouter(prefix="/orders", tags=["orders"])
readers = require_roles("owner", "accountant", "supervisor", "store")
writers = require_roles("owner", "accountant")


def _dated(db: Session, *orders: s.OrderOut) -> list[s.OrderOut]:
    """Fills in each order's delivery date and days late from the whole mill's schedule, built once. It is done here, not in
    the orders service, because the insights service already reads from the orders service (a call back would be circular)."""
    dates = insights.delivery_dates(db)
    return [o.model_copy(update={"delivery_date": dates[o.code][0], "days_late": dates[o.code][1]}) if o.code in dates else o
            for o in orders]


@router.get("", response_model=list[s.OrderOut], dependencies=[Depends(readers)])
def list_orders(state: str | None = None, buyer_id: int | None = None,
                db: Session = Depends(get_db)) -> list[s.OrderOut]:
    return _dated(db, *service.list_orders(db, state, buyer_id))


@router.post("", response_model=s.OrderOut, status_code=201, dependencies=[Depends(writers)])
def create_order(body: s.OrderIn, db: Session = Depends(get_db)) -> s.OrderOut:
    return _dated(db, service.order_out(db, service.create_order(db, body)))[0]


@router.get("/{order_code}", response_model=s.OrderOut, dependencies=[Depends(readers)])
def get_order(order_code: str, db: Session = Depends(get_db)) -> s.OrderOut:
    return _dated(db, service.order_out(db, service.get_order_or_404(db, order_code)))[0]


@router.post("/{order_code}/confirm", response_model=s.OrderOut, dependencies=[Depends(writers)])
def confirm_order(order_code: str, db: Session = Depends(get_db)) -> s.OrderOut:
    return _dated(db, service.order_out(db, service.confirm_order(db, order_code)))[0]


@router.post("/{order_code}/cancel", response_model=s.OrderOut, dependencies=[Depends(writers)])
def cancel_order(order_code: str, db: Session = Depends(get_db)) -> s.OrderOut:
    return _dated(db, service.order_out(db, service.cancel_order(db, order_code)))[0]


@router.patch("/{order_code}", response_model=s.OrderOut, dependencies=[Depends(writers)])
def change_deadline(order_code: str, body: s.DeadlineIn, db: Session = Depends(get_db)) -> s.OrderOut:
    return _dated(db, service.order_out(db, service.change_deadline(db, order_code, body)))[0]


@router.get("/{order_code}/yarn-check", response_model=s.YarnCheckOut, dependencies=[Depends(readers)])
def yarn_check(order_code: str, db: Session = Depends(get_db)) -> s.YarnCheckOut:
    return service.yarn_check(db, service.get_order_or_404(db, order_code))
```

- [ ] **Step 7: Run and watch them pass.** `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_insights_settings.py tests/test_insights_api.py -q`. Expected: `13 + 17 = 30 passed` (settings 13, API 17: the role test is parametrised four ways). If a figure is off, root-cause it with `systematic-debugging` against the hand-worked numbers in this plan; do not bend the expected number.

- [ ] **Step 8: Update the older tests** the full suite now shows failing because they read the example insights, ETA or order dates (run the suite once and look): expect `test_contract_trade.py`, `test_contract_asks.py`, `test_contract_store_orders.py` and possibly `test_llm_api.py`. Remove an example-data case where a real test now covers it, and change an assertion on a placeholder (`delivery_date is None`) to what is true now.

- [ ] **Step 9: Mutation-check** (revert after each):
  1. `orders/router.py`: make `_dated` return its orders unchanged: `test_the_order_list_and_detail_carry_the_real_dates` fails.
  2. `loader.py` `load_stages`: drop `Machine.id.not_in(down)`: `test_no_working_machine_at_a_stage_with_work_is_a_409_and_a_null_date` fails.
  3. `loader.py` `load_stages`: ignore `counts` (use all shifts): `test_an_extra_shift_what_if_appears_when_weaving_runs_two_of_three_shifts` fails.
  4. `loader.py` `load_yarn`: pass `None` instead of `supplier.lead_time_days`: `test_the_shortage_forecast_for_cotton` fails (no order-by date).
  5. `loader.py` `_efficiency_runs`: drop the `ProductionRun.ended_at >= since` condition: `test_a_run_that_ended_before_the_efficiency_window_is_ignored` fails; and return `[]` from it: `test_a_recent_slow_run_lowers_the_weaving_capacity` fails.
  6. `loader.py` `_shift_name`: return `None`: the `weaving_shift` row disappears from the root-cause test.
  7. `loader.py` `load_roll_facts`: count every inspected roll as defective: `test_root_causes_flag_the_group...` fails.
  8. `service.py` `late_orders`: drop the `days_late > 0` filter: `test_late_orders_lists_only_the_late_ones` fails.
  9. `service.py` `order_eta`: skip the `NOT_SCHEDULED` check: `test_an_order_not_waiting_for_production_is_a_409` fails.
  10. `service.py` `shortages`: skip the `result is None` check: the "empty mill" test and the blocked-lot test fail.

- [ ] **Step 10: Full suite twice.** Expected both times: about **1,334 passed** (1,304 + 30, less any example cases removed in Step 8).

- [ ] **Step 11: Sync and commit** (Status line with the real counts, header, then):

```bash
git add services/api docs/plans/B7-intelligence.md
git commit -m "Serve the real delivery dates, late orders, shortages and root causes"
```

---

### Task 5: The recall chain

**Files:**
- Create: `services/api/app/modules/insights/recall.py`
- Modify: `services/api/app/modules/store/router.py` (the recall route), `services/api/tests/insights_world.py` (append the recall mill)
- Test: create `services/api/tests/test_recall_api.py`; update older tests that read the example recall

**Interfaces:**
- Consumes: existing `store.service.get_lot_or_404`, `store.schemas.{RecallOut, RecallRoll, RecallBuyer}`, the view `v_roll_status`.
- Produces: `recall.lot_recall(db, lot_code) -> RecallOut`; the route `GET /lots/{lot_code}/recall` now takes `db`.

- [ ] **Step 1: Append the recall mill and write the failing tests**

Append to `services/api/tests/insights_world.py`:

```python
@dataclass
class RecallMill:
    lot: object
    rolls: dict
    sharma: object
    kavya: object
    loading_truck: object
    sent_truck: object


def build_recall_mill(db) -> RecallMill:
    """Lot L: 120 kg issued to spinning run S1; 50 kg issued to S2 and fully returned (net 0). S1 fed one weaving run that
    made six rolls: R1 dyeing, R2 and R3 in store, R4 dispatched (Sharma), R5 on a loading truck (Kavya), R6 rejected.
    S2 fed another weaving run whose roll R7 must NOT appear."""
    sharma, kavya = make_buyer(db, name="Sharma Fabrics"), make_buyer(db, name="Kavya Garments")
    order_s, order_k = make_order(db, buyer=sharma), make_order(db, buyer=kavya)
    lot = make_lot(db, qty_kg=500)
    mover = make_user(db, role="store").id
    s1 = make_run(db, order_s, make_machine(db, stage="spinning"), started_at=LONG_AGO, ended_at=LONG_AGO)
    s2 = make_run(db, order_s, make_machine(db, stage="spinning"), started_at=LONG_AGO, ended_at=LONG_AGO)
    for run, kg in ((s1, -120), (s2, -50), (s2, 50)):
        db.add(YarnMovement(yarn_lot_id=lot.id, kind="issue" if kg < 0 else "return", qty_kg=kg, production_run_id=run.id,
                            moved_by=mover))
    w1 = make_run(db, order_s, make_machine(db, stage="weaving"), input_run_id=s1.id, started_at=LONG_AGO)
    w2 = make_run(db, order_s, make_machine(db, stage="weaving"), input_run_id=s2.id, started_at=LONG_AGO)
    dyer = make_machine(db, stage="dyeing")
    open_dye = make_run(db, order_s, dyer, started_at=LONG_AGO)                      # still running: R1 is 'dyeing'
    done_dye = make_run(db, order_s, make_machine(db, stage="dyeing"), started_at=LONG_AGO, ended_at=LONG_AGO)
    rolls = {"R1": make_roll(db, order_s, w1, 100), "R2": make_roll(db, order_s, w1, 100),
             "R3": make_roll(db, order_s, w1, 100), "R4": make_roll(db, order_s, w1, 100),
             "R5": make_roll(db, order_k, w1, 100), "R6": make_roll(db, order_s, w1, 100),
             "R7": make_roll(db, order_s, w2, 100)}
    dye(db, rolls["R1"], open_dye)
    for key in ("R2", "R3", "R4", "R5", "R6", "R7"):
        dye(db, rolls[key], done_dye)
        make_inspection(db, rolls[key], "reject" if key == "R6" else "pass")
    sent = make_dispatch(db, sharma, state="dispatched", dispatched_at=dt.datetime(2026, 10, 9, tzinfo=dt.UTC))
    loading = make_dispatch(db, kavya)
    put_on_dispatch(db, rolls["R4"], sent)
    put_on_dispatch(db, rolls["R5"], loading)
    db.flush()
    return RecallMill(lot, rolls, sharma, kavya, loading, sent)
```

`services/api/tests/test_recall_api.py`:

```python
"""B7: the recall chain (spec 8.4) on the hand-worked lot in tests/insights_world.py."""
import pytest
from tests.factories import make_lot
from tests.insights_world import build_recall_mill


@pytest.fixture
def mill(db):
    return build_recall_mill(db)


def codes(rows):
    return [r["roll_code"] for r in rows]


def test_the_lot_is_traced_to_every_roll_and_grouped_by_where_it_is(client, login_as, mill):
    login_as("store")
    body = client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()
    r = {key: roll.code for key, roll in mill.rolls.items()}
    assert body["lot_code"] == mill.lot.lot_code and body["is_blocked"] is False
    assert codes(body["on_floor"]) == sorted([r["R1"], r["R6"]])                       # R6 is rejected but still in the mill
    assert codes(body["in_store"]) == sorted([r["R2"], r["R3"]])
    assert codes(body["loading"]) == [r["R5"]] and codes(body["dispatched"]) == [r["R4"]]
    assert r["R7"] not in codes(body["on_floor"] + body["in_store"] + body["loading"] + body["dispatched"])   # S2 netted to zero
    assert {x["roll_code"]: x["status"] for x in body["on_floor"]} == {r["R1"]: "dyeing", r["R6"]: "rejected"}
    assert body["loading"][0]["dispatch_code"] == mill.loading_truck.code and body["dispatched"][0]["dispatch_code"] == mill.sent_truck.code
    assert body["in_store"][0]["dispatch_code"] is None and body["dispatched"][0]["buyer_name"] == "Sharma Fabrics"


def test_the_buyers_are_counted_with_only_confirmed_trucks_listed(client, login_as, mill):
    login_as("owner")
    buyers = {b["buyer_name"]: b for b in client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()["buyers"]}
    assert buyers["Sharma Fabrics"]["roll_count"] == 5 and buyers["Sharma Fabrics"]["dispatched_roll_count"] == 1
    assert buyers["Sharma Fabrics"]["dispatch_codes"] == [mill.sent_truck.code]
    assert buyers["Kavya Garments"]["roll_count"] == 1 and buyers["Kavya Garments"]["dispatched_roll_count"] == 0
    assert buyers["Kavya Garments"]["dispatch_codes"] == []                            # her truck has not left yet


def test_blocking_the_lot_changes_the_flag_but_not_the_rolls(client, login_as, mill):
    login_as("store")
    before = client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()
    assert client.post(f"/api/lots/{mill.lot.lot_code}/block", json={"reason": "colour fault"}).status_code == 200
    after = client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()
    assert after["is_blocked"] is True and {k: v for k, v in after.items() if k != "is_blocked"} == {k: v for k, v in before.items() if k != "is_blocked"}


def test_a_lot_nobody_used_has_nothing_to_recall_and_an_unknown_lot_is_a_404(client, login_as, db, mill):
    unused = make_lot(db)
    login_as("owner")
    body = client.get(f"/api/lots/{unused.lot_code}/recall").json()
    assert body["on_floor"] == body["in_store"] == body["loading"] == body["dispatched"] == body["buyers"] == []
    assert client.get("/api/lots/L-9999/recall").status_code == 404


@pytest.mark.parametrize("role", ["supervisor", "accountant", "qc", "dispatch", "buyer"])
def test_only_store_and_owner_may_read_a_recall(client, login_as, mill, role):
    login_as(role)
    assert client.get(f"/api/lots/{mill.lot.lot_code}/recall").status_code == 403


def test_the_recall_and_the_passport_agree_about_which_rolls_used_the_lot(client, login_as, mill):
    """A roll is in the lot's recall exactly when the roll's passport lists the lot."""
    login_as("owner")
    in_recall = set()
    body = client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()
    for group in ("on_floor", "in_store", "loading", "dispatched"):
        in_recall |= set(codes(body[group]))
    for roll in mill.rolls.values():
        lots = [lot["lot_code"] for lot in client.get(f"/api/rolls/{roll.code}/passport").json()["yarn_lots"]]
        assert (mill.lot.lot_code in lots) == (roll.code in in_recall), roll.code
```

- [ ] **Step 2: Run and watch them fail.** `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_recall_api.py -q` → failures on the example recall.

- [ ] **Step 3: Write `recall.py`**

`services/api/app/modules/insights/recall.py`:

```python
"""Spec 8.4: where did the yarn of one lot end up? The passport's trace (roll -> weaving run -> spinning run -> lots) run
the other way: lot -> spinning runs with a net positive issue -> weaving runs fed by them -> the rolls they made."""
from sqlalchemy import column, func, select, table
from sqlalchemy.orm import Session

from app.core.money import to_float
from app.db.models import Dispatch, DispatchItem, ProductionRun, Roll, RollRun, YarnMovement
from app.modules.store.schemas import RecallBuyer, RecallOut, RecallRoll
from app.modules.store.service import get_lot_or_404

v_roll_status = table("v_roll_status", column("roll_id"), column("status"))
ON_THE_FLOOR = ("woven", "dyeing", "awaiting_qc", "awaiting_rework", "in_rework", "rejected")


def lot_recall(db: Session, lot_code: str) -> RecallOut:
    lot = get_lot_or_404(db, lot_code)
    net = func.sum(YarnMovement.qty_kg)
    spinning = set(db.scalars(
        select(YarnMovement.production_run_id).where(YarnMovement.yarn_lot_id == lot.id,
                                                      YarnMovement.kind.in_(("issue", "return")))
        .group_by(YarnMovement.production_run_id).having(net < 0)))
    weaving = set(db.scalars(select(ProductionRun.id).where(ProductionRun.stage == "weaving",
                                                            ProductionRun.input_run_id.in_(spinning or {0}))))
    rolls = list(db.scalars(select(Roll).join(RollRun, RollRun.roll_id == Roll.id)
                            .where(RollRun.purpose == "produce", RollRun.run_id.in_(weaving or {0})).order_by(Roll.code)))
    status = dict(db.execute(select(v_roll_status.c.roll_id, v_roll_status.c.status)
                             .where(v_roll_status.c.roll_id.in_([r.id for r in rolls] or {0}))).all())
    truck = {roll_id: (code, state) for roll_id, code, state in db.execute(
        select(DispatchItem.roll_id, Dispatch.code, Dispatch.state).join(Dispatch, Dispatch.id == DispatchItem.dispatch_id)
        .where(DispatchItem.roll_id.in_([r.id for r in rolls] or {0})))}
    out = RecallOut(lot_code=lot.lot_code, is_blocked=lot.is_blocked, on_floor=[], in_store=[], loading=[],
                    dispatched=[], buyers=[])
    buyers: dict[int, dict] = {}
    for roll in rolls:
        state = status.get(roll.id, "woven")
        code = truck.get(roll.id, (None, None))[0]
        row = RecallRoll(roll_code=roll.code, order_code=roll.order.code, buyer_name=roll.order.buyer.name,
                         metres=to_float(roll.metres), status=state, dispatch_code=code)
        (out.on_floor if state in ON_THE_FLOOR else getattr(out, state)).append(row)
        entry = buyers.setdefault(roll.order.buyer_id, {"name": roll.order.buyer.name, "rolls": 0, "gone": 0, "codes": set()})
        entry["rolls"] += 1
        if state == "dispatched":
            entry["gone"] += 1
            entry["codes"].add(code)
    out.buyers = [RecallBuyer(buyer_id=buyer_id, buyer_name=e["name"], roll_count=e["rolls"],
                              dispatched_roll_count=e["gone"], dispatch_codes=sorted(e["codes"]))
                  for buyer_id, e in sorted(buyers.items(), key=lambda kv: kv[1]["name"])]
    return out
```

- [ ] **Step 4: Point the route at it.** In `services/api/app/modules/store/router.py`: delete the line `from app.modules.store import examples as ex`; add `from app.modules.insights import recall` in the import block; and replace the handler with:

```python
def lot_recall(lot_code: str, db: Session = Depends(get_db)) -> s.RecallOut:
    return recall.lot_recall(db, lot_code)
```

(`grep -n "ex\." services/api/app/modules/store/router.py` must then show nothing.) Fix any older test that expected the example recall.

- [ ] **Step 5: Run and watch them pass.** Expected: `5 + 5 = 10 passed` (five single tests, and the role test parametrised five ways).

- [ ] **Step 6: Mutation-check** (`recall.py`; revert after each):
  1. Drop `.having(net < 0)` from the spinning-run query: `test_the_lot_is_traced...` fails (R7 appears) and the passport agreement test fails.
  2. Remove `"rejected"` from `ON_THE_FLOOR`: the grouping test fails (R6 is lost or the handler errors).
  3. Count a loading roll as dispatched in `buyers` (use `state in ("dispatched", "loading")`): `test_the_buyers_are_counted_with_only_confirmed_trucks_listed` fails.

- [ ] **Step 7: Full suite twice.** Expected both times: about **1,344 passed**.

- [ ] **Step 8: Sync and commit** (Status line, header, then):

```bash
git add services/api docs/plans/B7-intelligence.md
git commit -m "Serve the real recall chain for a yarn lot"
```

---

### Task 6: The buyer portal's real delivery date

Ridanshi built the portal backend on her branch (merged into `main` on 2026-10-10): the routes, the timeline, the trucks, the 404 rules and seven tests (`tests/test_contract_portal.py`). It reads `delivery_date` from `orders.order_out`, the **service** function, which cannot see the schedule (the schedule lives in insights, which already reads the orders service, so the dates are filled one layer up, in the orders router). So the portal would keep showing `null`. This task gives her portal service the date, nothing else.

**Files:**
- Modify: `services/api/app/modules/portal/service.py`
- Delete: `services/api/app/modules/portal/examples.py` (nothing imports it after her change; confirm with `grep -rn "portal.examples\|portal import examples" services/api`)
- Test: create `services/api/tests/test_portal_dates.py`

**Interfaces:**
- Consumes (Task 4): `insights.service.delivery_dates(db) -> dict[code, (date, days_late)]`.
- Produces: nothing new; `portal.service.{my_orders, my_order}` keep their signatures and the buyer now sees the real `delivery_date`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_portal_dates.py`:

```python
"""B7: the buyer portal shows the real delivery date. The portal itself is Ridanshi's; everything else about it (the
timeline, the trucks, the 404 rules, progress) is tested in tests/test_contract_portal.py."""
import datetime as dt

import pytest
from app.core.auth import COOKIE_NAME, create_token
from app.modules.llm import data as assistant_data
from app.modules.llm.data import ToolContext
from tests.factories import make_user
from tests.insights_world import build_mill

DAY = dt.timedelta(days=1)


@pytest.fixture
def mill(db):
    return build_mill(db)


def as_buyer(client, db, mill):
    user = make_user(db, role="buyer", buyer_id=mill.buyer.id)
    client.cookies.set(COOKIE_NAME, create_token(user.id))
    return user


def test_the_portal_shows_the_real_delivery_date(client, db, mill):
    as_buyer(client, db, mill)
    rows = {o["code"]: o for o in client.get("/api/portal/orders").json()}
    assert rows[mill.order_a.code]["delivery_date"] == str(mill.today + 4 * DAY)
    assert rows[mill.order_a.code]["deadline"] == str(mill.today + 3 * DAY)               # promised the 3rd day, expected the 4th
    assert rows[mill.order_b.code]["delivery_date"] == str(mill.today + 6 * DAY)
    assert client.get(f"/api/portal/orders/{mill.order_a.code}").json()["delivery_date"] == str(mill.today + 4 * DAY)


def test_the_buyer_and_the_staff_see_the_same_date(client, login_as, db, mill):
    as_buyer(client, db, mill)
    portal = {o["code"]: o["delivery_date"] for o in client.get("/api/portal/orders").json()}
    login_as("owner")
    staff = {o["code"]: o["delivery_date"] for o in client.get("/api/orders").json()}
    assert portal and portal == {code: staff[code] for code in portal}


def test_a_cancelled_order_is_listed_but_has_no_delivery_date(client, db, mill):
    mill.order_b.state = "cancelled"
    db.flush()
    as_buyer(client, db, mill)
    rows = {o["code"]: o for o in client.get("/api/portal/orders").json()}
    assert rows[mill.order_b.code]["delivery_date"] is None
    assert rows[mill.order_a.code]["delivery_date"] == str(mill.today + 4 * DAY)


def test_the_assistants_buyer_tools_get_the_date(db, mill):
    user = make_user(db, role="buyer", buyer_id=mill.buyer.id)
    ctx = ToolContext(db, user)
    assert {o["code"]: o["delivery_date"] for o in assistant_data.my_orders(ctx)}[mill.order_a.code] == str(mill.today + 4 * DAY)
    assert assistant_data.my_order(ctx, mill.order_a.code)["delivery_date"] == str(mill.today + 4 * DAY)
```

- [ ] **Step 2: Run and watch them fail.** `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_portal_dates.py -q` → the date assertions fail with `None` (and the assistant test with `None`).

- [ ] **Step 3: Give her portal service the date.** In `services/api/app/modules/portal/service.py`: add `from app.modules.insights import service as insights` to the imports; change `_summary` to take the dates and use them; and fetch the dates once per request in both public functions. Exactly:

```python
def _summary(db: Session, order: Order, dates: dict[str, tuple[dt.date, int]]) -> s.PortalOrder:
    out = orders.order_out(db, order)
    return s.PortalOrder(
        code=order.code, fabric=out.fabric_type.name, colour=order.colour, qty_metres=out.qty_metres, stage=out.stage,
        progress_pct=100.0 if out.stage == "dispatched" else _share_done(order, out.progress),
        deadline=order.deadline, delivery_date=dates[order.code][0] if order.code in dates else None)
```

In `my_orders`, add `dates = insights.delivery_dates(db)` before the query and return `[_summary(db, order, dates) for order in db.scalars(query)]`. In `my_order`, add `dates = insights.delivery_dates(db)` after the `order is None` check and call `_summary(db, order, dates)` in the final `return`. Then `git rm services/api/app/modules/portal/examples.py`.

- [ ] **Step 4: Run and watch them pass.** Expected: `4 passed`; then `uv run python -m pytest -p no:warnings -o addopts= tests/test_contract_portal.py -q`: her 7 tests still pass.

- [ ] **Step 5: Mutation-check** (`portal/service.py`; revert after each):
  1. Pass `{}` instead of the dates: `test_the_portal_shows_the_real_delivery_date` and the assistant test fail.
  2. Take the date of the wrong order (`next(iter(dates.values()))[0]`): the side-by-side test fails.

- [ ] **Step 6: Full suite twice.** Expected both times: about **1,348 passed** (1,344 + 4).

- [ ] **Step 7: Sync and commit** (Status line, header, then):

```bash
git add services/api docs/plans/B7-intelligence.md
git commit -m "Give the buyer portal the real delivery date"
```

---

### Task 7: Prove it on a real server, close B7

**Files:** modify this plan, `docs/plans/README.md`, the spec header (and §16 if anything new was learned), the team note, memory. No code unless the live check finds a bug (then fix it test-first and say so).

- [ ] **Step 1: Throwaway database and server.** Check `lsof -nP -iTCP:8000 -iTCP:3000 -iTCP:8123 -sTCP:LISTEN`; `export DATABASE_URL=postgresql+psycopg://localhost:5432/everest_livecheck`; `createdb everest_livecheck`; `npm run db:migrate && npm run db:seed && npm run db:demo`; start `cd services/api && uv run uvicorn app.main:app --host 127.0.0.1 --port 8123` in the background and drive it with `ctx_execute` Python over HTTP (curl is blocked by a hook).

- [ ] **Step 2: Delivery dates against an independent recalculation.** For the demo mill (three orders) read `GET /api/orders` and `GET /api/orders/{code}/eta`, then recompute each date from the raw tables with plain SQL and Python outside the engine (remaining work from the progress numbers, capacity from `machines` and `shifts` at efficiency 0.8, the deadline-ordered queue) and compare. Also set `STAGE_SHIFTS=weaving=2` in the server's environment, restart, and confirm a late order gets "Add a third shift on weaving" with the date the hand calculation gives.

- [ ] **Step 3: Shortage, root cause and recall.** Make the demo's low-yarn state real (the demo mill's order C is "short 230 kg") and read `/api/insights/shortages` against a hand calculation; seed a defect pattern through the real API (inspections with confirmed defects on rolls from one lot, enough rolls: at least ten) and read `/api/insights/root-causes`; block the demo's cotton lot (`POST /api/lots/{code}/block`) and read `/api/lots/{code}/recall`, checking every roll against the passport's lot list.

- [ ] **Step 4: The portal as the buyer and the role matrix.** As `buyer` (Sharma Fabrics): `GET /api/portal/orders` and the detail of an own order (delivery date equals the staff view's), another buyer's order and a nonexistent one give the identical 404, the raw text contains no machine, operator, lot, supplier or cost; every staff role gets 403 on the portal; every insight route against its roles; no login gives 401.

- [ ] **Step 5: The assistant's data functions.** From a Python shell on the same database call the assistant's data functions (`app.modules.llm.data`: `late_orders`, `order_eta`, `shortages`, `root_causes`, `lot_recall`, `my_orders`, `my_order`) with a real `ToolContext` and confirm each returns the real figures; no model is needed.

- [ ] **Step 6: Speed.** Build a synthetic busy mill on the throwaway database (about 200 confirmed orders with a few hundred runs and rolls, ten machines) and time `GET /api/orders` (which builds the whole schedule once), `GET /api/insights/late-orders` and `GET /api/insights/root-causes`; record the seconds in the Status line.

- [ ] **Step 7: Adversarial checklist, once, on the new code and on any fix made in this task:** zero or negative-looking values (an order with no work left, a reorder level of 0, a roll of the smallest metres); empty inputs (an empty mill, no shifts configured, no lots ever received, nothing inspected); jointly invalid inputs (a machine down and also running, overlapping shifts, a lot issued to two spinning runs); double submit and concurrency (not applicable: read-only; state this); identity change (a buyer after their order is cancelled); type and serialization (no NaN or infinity can reach the JSON: every float comes from a `Fraction` or `Decimal` conversion; an enormous p-value exponent); month, code and path inputs (an unknown lot, order or roll). Record what was checked and what was not applicable.

- [ ] **Step 8: Clean up and re-check the other half.** Stop the server, `dropdb everest_livecheck`, confirm nothing listens on 8123, 8000 or 3000 and only `everest` and `everest_test` remain. If Hritwik's servers are running, re-check `GET /api/floor`, `/api/orders` (now with dates), `/api/insights/late-orders` and `/api/portal/orders` as buyer (200s); his database needs no migration for B7.

- [ ] **Step 9: Close out.** Mark B7 complete in this plan (`Done when` all met) and in `docs/plans/README.md` (rows B7 and R1, R2); update the spec header and §16; write a note to Ridanshi at the top of `docs/HRITWIK_TEAM_NOTES.md` (the late, shortage, root-cause, recall and portal screens now show real data; `delivery_date` and `days_late` are real on orders; the `STAGE_SHIFTS` setting and what it does for the add-a-shift what-if; the portal rules and `progress_pct` meaning; the 409 codes `NOT_SCHEDULED` and `NO_CAPACITY` her screens may meet; the assistant's late, shortage, root-cause, recall and buyer tools now read real data); update the memory project state; run the authorship scan; commit; tell Hritwik to push.

```bash
git add docs
git commit -m "Close B7: the intelligence live check passed on a real server"
```

---

## Done when

- The full suite is green twice; the pure engines pass without a database; every mutation listed in Tasks 1-6 makes a test fail (a surviving one led to a stronger test).
- Delivery dates, the shortage forecast, the root causes and the recall agree with independent recalculations on a real server; the order list shows real dates; the exact test agrees with scipy (recorded in Status).
- The buyer portal shows the real delivery date, the same as the staff screens; the assistant's tools return real figures.
- `contracts/` is byte-identical; `docs/plans/README.md` marks B7 done; the plan's Status, the spec header, the team note and the memory are current; the speed figures are recorded.
