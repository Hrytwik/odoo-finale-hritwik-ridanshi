import datetime as dt

import pytest

from app.db.models import MachineDowntime, ProductionRun, QcDefect, QcInspection, RollRun
from tests.factories import make_machine, make_order, make_roll, make_run, make_worker
from tests.helpers import violates


def _weaving_run(db):
    order = make_order(db)
    return order, make_run(db, order, make_machine(db, stage="weaving"))


# ---- machines are never double-booked ------------------------------------------------------

def test_one_open_run_per_machine(db):
    order, loom = make_order(db), make_machine(db, stage="weaving")
    make_run(db, order, loom)
    with violates("uq_open_run_per_machine"):
        make_run(db, order, loom)


def test_ended_run_frees_the_machine(db):
    order, loom = make_order(db), make_machine(db, stage="weaving")
    run = make_run(db, order, loom)
    run.ended_at = run.started_at
    db.flush()
    assert make_run(db, order, loom).id


def test_one_open_downtime_per_machine(db):
    loom = make_machine(db)
    db.add(MachineDowntime(machine_id=loom.id, reason="belt snapped"))
    db.flush()
    with violates("uq_open_downtime_per_machine"):
        db.add(MachineDowntime(machine_id=loom.id, reason="again"))
        db.flush()


def test_a_repaired_machine_can_break_down_again(db):
    loom = make_machine(db)
    first = MachineDowntime(machine_id=loom.id, reason="belt snapped")
    db.add(first)
    db.flush()
    first.ended_at = first.started_at
    db.add(MachineDowntime(machine_id=loom.id, reason="motor"))
    db.flush()


def test_downtime_cannot_end_before_it_starts(db):
    d = MachineDowntime(machine_id=make_machine(db).id, reason="belt")
    db.add(d)
    db.flush()
    d.ended_at = d.started_at - dt.timedelta(minutes=1)
    with violates("ck_machine_downtimes_end_after_start"):
        db.flush()


def test_downtime_needs_a_reason(db):
    with violates("ck_machine_downtimes_reason_nonblank"):
        db.add(MachineDowntime(machine_id=make_machine(db).id, reason="   "))
        db.flush()


# ---- production runs ----------------------------------------------------------------------

def test_weaving_run_needs_input_run(db):
    order, loom, op = make_order(db), make_machine(db, stage="weaving"), make_worker(db)
    with violates("ck_production_runs_weaving_input"):
        db.add(ProductionRun(order_id=order.id, machine_id=loom.id, stage="weaving", operator_worker_id=op.id))
        db.flush()


def test_only_weaving_runs_may_have_an_input_run(db):
    order, dyer = make_order(db), make_machine(db, stage="dyeing")
    _, weave = _weaving_run(db)
    with violates("ck_production_runs_weaving_input"):
        make_run(db, order, dyer, input_run_id=weave.id)


def test_only_rework_may_have_no_machine(db):
    order, op = make_order(db), make_worker(db)
    with violates("ck_production_runs_machine_required"):
        db.add(ProductionRun(order_id=order.id, stage="dyeing", operator_worker_id=op.id))
        db.flush()


def test_manual_rework_run_without_a_machine_is_allowed(db):
    order, op = make_order(db), make_worker(db)
    db.add(ProductionRun(order_id=order.id, stage="rework", operator_worker_id=op.id))
    db.flush()


def test_output_kg_only_on_spinning(db):
    order, dyer = make_order(db), make_machine(db, stage="dyeing")
    run = make_run(db, order, dyer)
    run.output_kg = 10
    with violates("ck_production_runs_output_spinning_only"):
        db.flush()


def test_spinning_output_cannot_be_negative(db):
    order, spinner = make_order(db), make_machine(db, stage="spinning")
    run = make_run(db, order, spinner)
    run.output_kg = -1
    with violates("ck_production_runs_output_spinning_only"):
        db.flush()


def test_run_cannot_end_before_it_starts(db):
    order, loom = make_order(db), make_machine(db, stage="weaving")
    run = make_run(db, order, loom)
    run.ended_at = run.started_at - dt.timedelta(minutes=1)
    with violates("ck_production_runs_end_after_start"):
        db.flush()


def test_a_zero_length_run_is_allowed(db):
    # an immediate breakdown or hand-over ends a run at the very moment it started
    order, loom = make_order(db), make_machine(db, stage="weaving")
    run = make_run(db, order, loom)
    run.ended_at = run.started_at
    db.flush()


def test_run_stage_must_be_known(db):
    order, op = make_order(db), make_worker(db)
    with violates("ck_production_runs_stage_valid"):
        db.add(ProductionRun(order_id=order.id, machine_id=make_machine(db).id, stage="knitting",
                             operator_worker_id=op.id))
        db.flush()


# ---- rolls --------------------------------------------------------------------------------

def test_roll_metres_must_be_positive(db):
    order, run = _weaving_run(db)
    with violates("ck_rolls_metres_pos"):
        make_roll(db, order, run, metres=0)


def test_roll_codes_are_unique(db):
    order, run = _weaving_run(db)
    roll = make_roll(db, order, run)
    with violates("uq_rolls_code"):
        db.add(type(roll)(code=roll.code, order_id=order.id, metres=10))
        db.flush()


def test_a_roll_cannot_be_linked_to_the_same_run_twice(db):
    order, run = _weaving_run(db)
    roll = make_roll(db, order, run)
    with violates("pk_roll_runs"):
        db.add(RollRun(roll_id=roll.id, run_id=run.id, purpose="dye"))
        db.flush()


def test_roll_run_purpose_must_be_known(db):
    order, run = _weaving_run(db)
    roll = make_roll(db, order, run)
    other = make_run(db, order, make_machine(db, stage="dyeing"))
    with violates("ck_roll_runs_purpose_valid"):
        db.add(RollRun(roll_id=roll.id, run_id=other.id, purpose="bogus"))
        db.flush()


# ---- quality checks -----------------------------------------------------------------------

def _inspection(db, **kw):
    order, run = _weaving_run(db)
    roll = make_roll(db, order, run)
    insp = QcInspection(**{"roll_id": roll.id, "inspector_worker_id": make_worker(db, role="inspector").id,
                           "verdict": "rework", **kw})
    db.add(insp)
    db.flush()
    return insp


def test_inspection_with_defects_saves(db):
    insp = _inspection(db)
    db.add(QcDefect(inspection_id=insp.id, defect_type="hole", count=2))
    db.flush()
    assert insp.overrode_ai is False


def test_verdict_must_be_known(db):
    with violates("ck_qc_inspections_verdict_valid"):
        _inspection(db, verdict="maybe")


def test_defect_count_must_be_positive(db):
    insp = _inspection(db)
    with violates("ck_qc_defects_count_pos"):
        db.add(QcDefect(inspection_id=insp.id, defect_type="hole", count=0))
        db.flush()


def test_defect_type_must_be_known(db):
    insp = _inspection(db)
    with violates("ck_qc_defects_type_valid"):
        db.add(QcDefect(inspection_id=insp.id, defect_type="torn", count=1))
        db.flush()


# ---- orders -------------------------------------------------------------------------------

@pytest.mark.parametrize("kw,constraint", [
    ({"qty_metres": 0}, "ck_orders_qty_pos"),
    ({"qty_metres": -5}, "ck_orders_qty_pos"),
    ({"price_per_metre": 0}, "ck_orders_price_pos"),
    ({"state": "shipped"}, "ck_orders_state_valid"),
    ({"state": "confirmed", "confirmed_at": None}, "ck_orders_confirmed_has_time"),
    ({"colour": "   "}, "ck_orders_colour_nonblank"),
    ({"code": "  "}, "ck_orders_code_nonblank"),
])
def test_order_rules(db, kw, constraint):
    with violates(constraint):
        make_order(db, **kw)


def test_order_codes_are_unique(db):
    first = make_order(db)
    with violates("uq_orders_code"):
        make_order(db, code=first.code)


def test_a_draft_order_needs_no_confirmation_time(db):
    assert make_order(db, state="draft").confirmed_at is None
