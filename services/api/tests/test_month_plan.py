"""B9 Task 2: the scheduler's own invariants, without a database."""
import datetime as dt
from collections import defaultdict

import pytest

from scripts.month.plan import IST, LOOMS, ORDERS, Roster, boundaries, build_plan, shift_of

END = dt.datetime(2026, 10, 11, 2, 0, tzinfo=IST)


@pytest.fixture(scope="module")
def plan():
    return build_plan(END, seed=11)


def at(day, hour, minute=0):
    return dt.datetime(2026, 10, day, hour, minute, tzinfo=IST)


def test_a_night_shift_is_dated_by_the_day_it_starts():
    assert shift_of(at(10, 22)) == ("C", dt.date(2026, 10, 10))
    assert shift_of(at(11, 1)) == ("C", dt.date(2026, 10, 10))
    assert shift_of(at(11, 5, 59)) == ("C", dt.date(2026, 10, 10))
    assert shift_of(at(11, 6)) == ("A", dt.date(2026, 10, 11))
    assert shift_of(at(11, 14)) == ("B", dt.date(2026, 10, 11))


def test_boundaries_are_strictly_inside_the_interval():
    assert boundaries(at(10, 5), at(11, 7)) == [at(10, 6), at(10, 14), at(10, 22), at(11, 6)]
    assert boundaries(at(10, 6), at(10, 14)) == []


def test_the_roster_always_has_an_operator_in_every_shift():
    roster = Roster(dt.date(2026, 9, 11), 31, seed=3)
    for d in range(31):
        for shift in "ABC":
            assert roster.present(shift, dt.date(2026, 9, 11) + dt.timedelta(days=d))


def test_same_seed_same_plan_and_a_different_seed_differs():
    a, b, c = build_plan(END, seed=11), build_plan(END, seed=11), build_plan(END, seed=12)
    assert [(e.t, e.action, e.args) for e in a.events] == [(e.t, e.action, e.args) for e in b.events]
    assert [(e.t, e.action) for e in a.events] != [(e.t, e.action) for e in c.events]


def test_events_are_in_time_order_and_none_is_after_the_end(plan):
    keys = [(e.t, e.seq) for e in plan.events]
    assert keys == sorted(keys) and all(e.t <= END for e in plan.events)


def assert_runs_never_overlap(events):
    open_run = {}
    for e in events:
        m = e.args.get("machine")
        if e.action in ("start_run", "rework_start") and m:
            assert m not in open_run, f"{m} started while a run is open at {e.t}"
            open_run[m] = e.t
        elif e.action == "handover":
            assert m in open_run, f"hand-over on {m} with no open run at {e.t}"
        elif e.action == "end_run" and m:
            assert m in open_run, f"end on {m} with no open run at {e.t}"
            del open_run[m]
        elif e.action in ("roll_off", "issue_yarn", "load_rolls"):
            assert m in open_run, f"{e.action} on {m} with no open run at {e.t}"


def test_a_machine_is_never_double_booked_and_runs_open_and_close_in_order(plan):
    assert_runs_never_overlap(plan.events)


def test_three_orders_arriving_together_queue_for_two_ring_frames_and_two_dyers():
    from scripts.month.plan import OrderSpec
    orders = [OrderSpec(f"X{i}", "Sharma Fabrics", "Poplin 58in", "navy", 3000, 120, 5, 12) for i in range(3)]
    stress = build_plan(dt.datetime(2026, 10, 11, 2, 0, tzinfo=IST), seed=11, orders=orders)
    assert_runs_never_overlap(stress.events)
    starts = sorted(e.t for e in stress.events if e.action == "start_run" and e.args["run_key"]
                    and e.args["run_key"].startswith("spin:") and not e.args["run_key"].endswith(":r"))   # not the re-make batches
    assert len(starts) == 3 and starts[2] - starts[0] > dt.timedelta(hours=10)      # the third waited for a ring frame


def test_a_breakdown_never_hits_a_busy_machine_and_nothing_starts_on_a_machine_that_is_down(plan):
    busy, down = set(), set()
    for e in plan.events:
        m = e.args.get("machine")
        if e.action in ("start_run", "rework_start") and m:
            assert m not in down, f"{m} started a run while down at {e.t}"
            busy.add(m)
        elif e.action == "end_run" and m:
            busy.discard(m)
        elif e.action == "breakdown":
            assert m not in busy, f"{m} broke down in the middle of a run at {e.t}"
            down.add(m)
        elif e.action == "repair":
            assert m in down
            down.discard(m)


def test_every_run_names_an_operator_who_is_present_that_shift(plan):
    for e in plan.events:
        if e.action in ("start_run", "rework_start", "handover") and e.args.get("operator"):
            shift, date = shift_of(e.t)
            assert plan.roster.status(e.args["operator"], shift, date) == "present", (e.action, e.t, e.args)


def test_a_handover_always_changes_the_operator(plan):
    current = {}
    for e in plan.events:
        m = e.args.get("machine")
        if e.action in ("start_run", "rework_start") and m:
            current[m] = e.args["operator"]
        elif e.action == "handover":
            assert e.args["operator"] != current[m], (m, e.t)
            current[m] = e.args["operator"]


def test_attendance_is_marked_for_every_shift_dated_up_to_the_ends_own_date(plan):
    """Including the shifts still to come today, so the machines running at the end stay covered."""
    marked = {(e.args["date"], e.args["shift"]) for e in plan.events if e.action == "attendance"}
    day = plan.day0.date()
    while day <= END.date():
        for shift in "ABC":
            assert (day, shift) in marked, (day, shift)
        day += dt.timedelta(days=1)
    assert max(d for d, _s in marked) == END.date()
    assert all(e.t <= END for e in plan.events if e.action == "attendance")      # none dated after the end


def test_weaving_starts_only_after_its_spinning_has_ended(plan):
    spin_end, open_spin = {}, {}
    weaving_starts = 0
    for e in plan.events:
        if e.action == "start_run" and e.args["run_key"] and e.args["run_key"].startswith("spin:"):
            open_spin[e.args["machine"]] = e.args["run_key"]
        elif e.action == "end_run" and e.args["machine"] in open_spin:
            spin_end[open_spin.pop(e.args["machine"])] = e.t
        elif e.action == "start_run" and e.args["input_key"]:
            weaving_starts += 1
            assert e.args["input_key"] in spin_end and spin_end[e.args["input_key"]] <= e.t
    assert weaving_starts > 10


def test_a_rolls_life_runs_in_order_and_dispatch_takes_only_passed_rolls(plan):
    roll_off, loaded, inspections, rework_started = {}, {}, defaultdict(list), {}
    scanned = {}
    for e in plan.events:
        r = e.args.get("roll")
        if e.action == "roll_off":
            roll_off[r] = e.t
        elif e.action == "load_rolls":
            for key in e.args["rolls"]:
                assert key in roll_off and roll_off[key] <= e.t
                loaded[key] = e.t
        elif e.action == "inspect":
            assert r in loaded and loaded[r] <= e.t
            inspections[r].append((e.t, e.args["verdict"]))
            assert len(inspections[r]) <= 2
            if len(inspections[r]) == 2:
                assert inspections[r][0][1] == "rework" and r in rework_started and rework_started[r] <= e.t
            if e.args["verdict"] != "pass":
                assert e.args["defects"]
        elif e.action == "rework_start":
            assert inspections[r] and inspections[r][-1][1] == "rework"
            rework_started[r] = e.t
        elif e.action == "dispatch_scan":
            assert inspections[r][-1][1] == "pass", f"{r} dispatched without a final pass"
            assert r not in scanned
            scanned[r] = e.t
    assert scanned, "no roll was ever dispatched"


def test_a_truck_is_scanned_before_it_is_confirmed(plan):
    created, last_scan, confirmed = {}, {}, {}
    for e in plan.events:
        k = e.args.get("truck")
        if e.action == "dispatch_create":
            created[k] = e.t
        elif e.action == "dispatch_scan":
            assert k in created
            last_scan[k] = e.t
        elif e.action == "dispatch_confirm":
            assert k in last_scan and last_scan[k] <= e.t
            confirmed[k] = e.t
    assert confirmed


def test_the_orders_and_their_states(plan):
    created = [e.args["order"] for e in plan.events if e.action == "create_order"]
    assert len(created) == len(ORDERS)
    cancelled = [e.args["order"] for e in plan.events if e.action == "cancel_order"]
    assert cancelled == ["O14"]
    confirmed = {e.args["order"] for e in plan.events if e.action == "confirm_order"}
    assert "O13" not in confirmed and "O14" in confirmed          # the draft is never confirmed; the cancelled one was


def test_the_month_is_the_size_that_was_designed():
    assert sum(o.metres for o in ORDERS if o.state == "confirmed") == 39500


def test_three_orders_are_in_progress_at_the_end(plan):
    last_dispatch, started = {}, set()
    for e in plan.events:
        if e.action == "start_run" and e.args["order"]:
            started.add(e.args["order"])
        if e.action == "dispatch_confirm":
            last_dispatch[e.args["order"]] = e.t
    open_orders = [o for o in started if o not in last_dispatch]
    assert len(open_orders) >= 3, open_orders


def test_the_idle_loom_is_never_planned_and_the_last_order_has_no_yarn_yet(plan):
    machines = {e.args["machine"] for e in plan.events if e.action in ("start_run", "rework_start") and e.args.get("machine")}
    assert "LOOM-06" not in machines and "LOOM-06" not in LOOMS
    o12 = [e for e in plan.events if e.args.get("order") == "O12"]
    assert [e.action for e in o12] == ["create_order", "confirm_order"]       # no lot, no run: the shortage story


def test_the_bad_lot_reaches_both_buyers(plan):
    lots = [e for e in plan.events if e.action == "receive_lot" and e.args["lot"] == "lot:bad"]
    assert len(lots) == 1
    issued = [e for e in plan.events if e.action == "issue_yarn" and e.args["lot"] == "lot:bad"]
    assert len(issued) == 2
    buyers = {e.args["buyer"] for e in plan.events if e.action == "create_order" and e.args["order"] in ("O7", "O8")}
    assert buyers == {"Sharma Fabrics", "Kavya Garments"}
    trucks = {e.args["truck"]: e.args["buyer"] for e in plan.events if e.action == "dispatch_create"}
    scans = [e for e in plan.events if e.action == "dispatch_scan" and e.args["roll"].startswith(("roll:O7:", "roll:O8:"))
             and ":r:" not in e.args["roll"]]                          # the lot's own rolls, not the re-made ones from another lot
    assert scans and {trucks[e.args["truck"]] for e in scans} == buyers


def test_buyers_pay_some_trucks_and_one_payment_is_partial(plan):
    payments = [e for e in plan.events if e.action == "buyer_payment"]
    trucks = [e for e in plan.events if e.action == "dispatch_confirm"]
    assert 3 <= len(payments) < len(trucks)                       # some paid, the latest still unpaid
    assert sum(1 for e in payments if e.args["fraction"] == 0.5) == 1
    confirmed = {e.args["truck"]: e.t for e in trucks}
    assert all(e.t > confirmed[e.args["truck"]] for e in payments)    # nobody pays before the truck is confirmed


def test_the_first_lot_arrives_before_the_month_and_is_never_paid(plan):
    lots = {e.args["lot"]: e for e in plan.events if e.action == "receive_lot"}
    assert lots["lot:O1"].t < plan.day0                                 # the opening stock: its bill falls due inside the month
    paid = {e.args["lot"] for e in plan.events if e.action == "supplier_payment"}
    assert "lot:O1" not in paid and paid == {"lot:O2", "lot:O3"}


def test_rejected_metres_are_re_made_so_a_finished_order_reaches_its_ordered_metres(plan):
    """An order is complete only when its good metres reach the ordered metres: a roll that is rejected is woven again."""
    metres = {e.args["roll"]: e.args["metres"] for e in plan.events if e.action == "roll_off"}
    scanned = defaultdict(float)
    for e in plan.events:
        if e.action == "dispatch_scan":
            scanned[e.args["roll"].split(":")[1]] += metres[e.args["roll"]]
    ordered = {o.key: o.metres for o in ORDERS}
    for key in ("O1", "O2", "O3", "O4", "O5"):                    # the orders long finished by the end of the month
        assert scanned[key] >= ordered[key], (key, scanned[key], ordered[key])
    assert any(":r:" in e.args["roll"] for e in plan.events if e.action == "roll_off"), "no replacement batch was ever made"


@pytest.mark.parametrize("hour,minute", [(0, 5), (3, 0), (6, 23), (6, 31), (7, 8), (9, 59), (12, 0), (15, 30), (18, 0), (21, 45), (23, 55)])
def test_a_truck_is_still_loading_whenever_in_the_day_the_month_is_built(hour, minute):
    """The jury demo runs at a different time of day than the build was tried at; "a truck still loading" must not depend on it."""
    end = dt.datetime(2026, 10, 11, hour, minute, tzinfo=IST)
    events = build_plan(end, seed=11).events
    created = {e.args["truck"] for e in events if e.action == "dispatch_create"}
    confirmed = {e.args["truck"] for e in events if e.action == "dispatch_confirm"}
    scanned = {e.args["truck"] for e in events if e.action == "dispatch_scan"}
    loading = created - confirmed
    assert len(loading) == 1, f"{len(loading)} trucks loading at {end:%H:%M}"
    assert loading <= scanned, "the loading truck has rolls on it"


@pytest.mark.parametrize("hour,minute", [(0, 5), (6, 23), (7, 8), (8, 1), (9, 59), (12, 0), (18, 0), (23, 55)])
def test_a_machine_is_down_and_not_yet_repaired_whenever_in_the_day_the_month_is_built(hour, minute):
    """Same family as the loading truck: "a down machine now" is relative to the end moment, not to a clock hour of the day."""
    end = dt.datetime(2026, 10, 11, hour, minute, tzinfo=IST)
    down = set()
    for e in build_plan(end, seed=11).events:
        if e.action == "breakdown":
            down.add(e.args["machine"])
        elif e.action == "repair":
            down.discard(e.args["machine"])
    assert down == {"SPIN-02"}, f"machines down at {end:%H:%M}: {sorted(down)}"
