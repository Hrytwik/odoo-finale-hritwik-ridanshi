"""B3 Task 2: floor board, machine page, run list, machine status and 'output today' (India-time day).
Hand-worked numbers: spinning 640 kg today (100 yesterday); weaving 100+120+80 = 300 m today (50 yesterday);
dyeing 300+200 = 500 m in a dye run ended today; order 5,000 m / 0.12 kg per m / 5% wastage -> need 630 kg."""
import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import event

from app.core.clock import today_ist
from app.db.models import MachineDowntime
from tests.factories import (
    dye, make_fabric_type, make_machine, make_order, make_roll, make_run, make_worker, make_yarn_type,
)

IST = ZoneInfo("Asia/Kolkata")


def ist(day_offset: int, hour: int, minute: int = 0) -> dt.datetime:
    d = today_ist() + dt.timedelta(days=day_offset)
    return dt.datetime(d.year, d.month, d.day, hour, minute, tzinfo=IST)


def board(client):
    r = client.get("/api/floor")
    assert r.status_code == 200, r.text
    return r.json()


def card(client, machine):
    return next(m for m in board(client)["machines"] if m["code"] == machine.code)


@pytest.fixture
def sup(login_as):
    return login_as("supervisor")


# ---- status and counts ----------------------------------------------------------------------

def test_status_down_beats_running_beats_idle_and_counts_add_up(client, db, sup):
    order = make_order(db)
    running, down, idle = (make_machine(db, stage="spinning") for _ in range(3))
    make_run(db, order, running)
    make_run(db, order, down)
    db.add(MachineDowntime(machine_id=down.id, reason="belt snapped", started_at=ist(0, 6)))
    db.flush()
    b = board(client)
    assert {m["code"]: m["status"] for m in b["machines"]} == {
        running.code: "running", down.code: "down", idle.code: "idle"}
    assert (b["running"], b["idle"], b["down"]) == (1, 1, 1) and len(b["machines"]) == 3
    assert b["generated_at"]


def test_a_machine_with_an_ended_run_and_a_closed_downtime_is_idle(client, db, sup):
    m = make_machine(db, stage="spinning")
    make_run(db, make_order(db), m, started_at=ist(-1, 8), ended_at=ist(-1, 9))
    db.add(MachineDowntime(machine_id=m.id, reason="x", started_at=ist(-1, 10), ended_at=ist(-1, 11)))
    db.flush()
    assert card(client, m)["status"] == "idle"


def test_inactive_machines_are_off_the_board_and_have_no_page(client, db, sup):
    on, off = make_machine(db, stage="weaving"), make_machine(db, stage="weaving", active=False)
    codes = [m["code"] for m in board(client)["machines"]]
    assert on.code in codes and off.code not in codes
    assert client.get(f"/api/machines/{off.code}").status_code == 404
    r = client.get("/api/machines/NOPE-99")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND" and r.json()["field"] == "machine_code"


def test_the_board_is_ordered_by_stage_then_code(client, db, sup):
    for stage, code in (("dyeing", "D-1"), ("weaving", "W-2"), ("spinning", "S-9"), ("weaving", "W-1"),
                        ("spinning", "S-1")):
        make_machine(db, stage=stage, code=code)
    assert [m["code"] for m in board(client)["machines"]] == ["S-1", "S-9", "W-1", "W-2", "D-1"]


# ---- output today (India-time day) ------------------------------------------------------------

def test_spinning_output_today_counts_runs_ended_today_only(client, db, sup):
    m, order = make_machine(db, stage="spinning"), make_order(db)
    make_run(db, order, m, started_at=ist(0, 1), ended_at=ist(0, 5), output_kg=Decimal("640"))
    make_run(db, order, m, started_at=ist(-1, 1), ended_at=ist(-1, 5), output_kg=Decimal("100"))
    c = card(client, m)
    assert c["output_today"] == 640.0 and c["output_unit"] == "kg"


def test_an_open_spinning_run_counts_nothing_yet(client, db, sup):
    m = make_machine(db, stage="spinning")
    make_run(db, make_order(db), m, started_at=ist(0, 1))
    assert card(client, m)["output_today"] == 0.0


def test_weaving_output_today_is_the_metres_of_rolls_made_today(client, db, sup):
    m, order = make_machine(db, stage="weaving"), make_order(db)
    run = make_run(db, order, m)
    for metres in (100, 120, 80):
        make_roll(db, order, run, metres)
    old = make_roll(db, order, run, 50)
    old.created_at = ist(-1, 12)
    db.flush()
    c = card(client, m)
    assert c["output_today"] == 300.0 and c["output_unit"] == "m"


def test_dyeing_output_today_counts_rolls_in_dye_runs_ended_today(client, db, sup):
    m, order = make_machine(db, stage="dyeing"), make_order(db)
    weave = make_run(db, order, make_machine(db, stage="weaving"))
    done = make_run(db, order, m, started_at=ist(0, 1), ended_at=ist(0, 6))
    for metres in (300, 200):
        dye(db, make_roll(db, order, weave, metres), done)
    yesterday = make_run(db, order, m, started_at=ist(-1, 1), ended_at=ist(-1, 6))
    dye(db, make_roll(db, order, weave, 999), yesterday)
    open_run = make_run(db, order, m, started_at=ist(0, 7))
    dye(db, make_roll(db, order, weave, 100), open_run)
    c = card(client, m)
    assert c["output_today"] == 500.0 and c["output_unit"] == "m"


def test_the_day_is_the_india_day_not_the_utc_day(client, db, sup):
    """23:30 IST yesterday is 18:00 UTC yesterday; 00:30 IST today is 19:00 UTC YESTERDAY too: same UTC date,
    different India dates. Only the second belongs to 'today'."""
    m, order = make_machine(db, stage="spinning"), make_order(db)
    make_run(db, order, m, started_at=ist(-1, 20), ended_at=ist(-1, 23, 30), output_kg=Decimal("100"))
    make_run(db, order, m, started_at=ist(0, 0, 10), ended_at=ist(0, 0, 30), output_kg=Decimal("7"))
    assert card(client, m)["output_today"] == 7.0


def test_a_machine_with_no_runs_shows_zero_not_null(client, db, sup):
    m = make_machine(db, stage="weaving")
    assert card(client, m)["output_today"] == 0.0


# ---- current run, downtime, order_progress_pct --------------------------------------------------

def order_5000(db):
    cotton = make_yarn_type(db)
    return make_order(db, fabric_type=make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.12, wastage_pct=5),
                      qty_metres=5000)


def test_the_current_run_and_the_downtime_are_shown(client, db, sup):
    order, worker = order_5000(db), make_worker(db, name="Ravi Kumar")
    m = make_machine(db, stage="spinning")
    run = make_run(db, order, m, operator=worker, started_at=ist(0, 6))
    c = card(client, m)
    cur = c["current_run"]
    assert (cur["id"], cur["order_code"], cur["stage"]) == (run.id, order.code, "spinning")
    assert cur["operator"] == {"id": worker.id, "name": "Ravi Kumar"} and cur["started_at"]
    assert c["downtime"] is None
    broken = make_machine(db, stage="weaving")
    db.add(MachineDowntime(machine_id=broken.id, reason="bearing", started_at=ist(0, 7)))
    db.flush()
    d = card(client, broken)
    assert d["status"] == "down" and d["downtime"]["reason"] == "bearing" and d["current_run"] is None


def pct(client, machine):
    return card(client, machine)["current_run"]["order_progress_pct"]


def test_spinning_progress_is_spun_over_need(client, db, sup):
    order, m = order_5000(db), make_machine(db, stage="spinning")
    make_run(db, order, make_machine(db, stage="spinning"), started_at=ist(-1, 1), ended_at=ist(-1, 5),
             output_kg=Decimal("315"))
    make_run(db, order, m, started_at=ist(0, 1))
    assert pct(client, m) == 50.0                       # 315 of 630 kg


def test_weaving_progress_is_woven_over_ordered_metres(client, db, sup):
    order, m = order_5000(db), make_machine(db, stage="weaving")
    run = make_run(db, order, m)
    make_roll(db, order, run, 2000)
    make_roll(db, order, run, 310)
    assert pct(client, m) == 46.2                       # 2,310 of 5,000 m


def test_dyeing_progress_is_dyed_over_ordered_metres(client, db, sup):
    order, m = order_5000(db), make_machine(db, stage="dyeing")
    weave = make_run(db, order, make_machine(db, stage="weaving"))
    finished = make_run(db, order, make_machine(db, stage="dyeing"), started_at=ist(-1, 1), ended_at=ist(-1, 5))
    dye(db, make_roll(db, order, weave, 1540), finished)
    make_run(db, order, m, started_at=ist(0, 1))
    assert pct(client, m) == 30.8                       # 1,540 of 5,000 m


def test_progress_is_capped_at_100(client, db, sup):
    order, m = order_5000(db), make_machine(db, stage="weaving")
    make_roll(db, order, make_run(db, order, m), 5500)
    assert pct(client, m) == 100.0


def test_progress_is_zero_when_there_is_nothing_to_divide_by(client, db, sup):
    order = make_order(db, fabric_type=make_fabric_type(db))
    order.fabric_type.recipe_lines.clear()
    db.flush()
    m = make_machine(db, stage="spinning")
    make_run(db, order, m)
    assert pct(client, m) == 0.0                        # need_kg is 0


# ---- machine page ----------------------------------------------------------------------------

def test_the_machine_page_has_the_card_and_the_last_ten_runs_newest_first(client, db, sup):
    m, order = make_machine(db, stage="spinning"), make_order(db)
    runs = [make_run(db, order, m, started_at=ist(-3, h), ended_at=ist(-3, h, 30)) for h in range(1, 13)]
    r = client.get(f"/api/machines/{m.code}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == m.code and body["status"] == "idle"
    assert [x["id"] for x in body["recent_runs"]] == [x.id for x in reversed(runs)][:10]


# ---- run list ------------------------------------------------------------------------------------

def test_runs_list_filters_orders_and_shows_rolls(client, db, sup):
    order, other = make_order(db), make_order(db)
    spin_m = make_machine(db, stage="spinning")
    spin = make_run(db, order, spin_m, started_at=ist(-1, 1), ended_at=ist(-1, 5), output_kg=Decimal("590"))
    weave_m = make_machine(db, stage="weaving")
    weave = make_run(db, order, weave_m, input_run_id=spin.id, started_at=ist(0, 1))
    r1, r2 = make_roll(db, order, weave, 100), make_roll(db, order, weave, 120)
    make_run(db, other, make_machine(db, stage="spinning"), started_at=ist(0, 2))
    runs = client.get(f"/api/runs?order_code={order.code}").json()
    assert [r["id"] for r in runs] == [weave.id, spin.id]                      # newest first, ended runs included
    w, s = runs
    assert w["roll_codes"] == [r1.code, r2.code] and w["metres"] == 220.0 and w["input_run_id"] == spin.id
    assert w["machine_code"] == weave_m.code and w["ended_at"] is None and w["output_kg"] is None
    assert s["output_kg"] == 590.0 and s["roll_codes"] == [] and s["metres"] == 0.0 and s["ended_at"]
    assert s["order_code"] == order.code and s["operator"]["id"] == spin.operator_worker_id
    only = client.get(f"/api/runs?order_code={order.code}&stage=weaving").json()
    assert [r["id"] for r in only] == [weave.id]
    assert client.get("/api/runs?order_code=ORD-9999999").json() == []
    assert client.get("/api/runs?stage=sewing").status_code == 422


# ---- roles and cost ------------------------------------------------------------------------------------

@pytest.mark.parametrize("role, ok", [("supervisor", True), ("owner", True), ("accountant", True),
                                      ("store", False), ("qc", False), ("dispatch", False), ("buyer", False)])
def test_who_can_read_the_floor(client, db, login_as, role, ok):
    login_as(role)
    m = make_machine(db, stage="spinning")
    make_run(db, make_order(db), m)
    for path in ("/api/floor", f"/api/machines/{m.code}", "/api/runs"):
        assert (client.get(path).status_code == 200) is ok, path


def test_idle_machines_cost_no_extra_queries(client, db, sup):
    """The board reads status, runs, downtimes and output for ALL machines at once, not per machine."""
    count = []
    engine = db.get_bind()

    def tick(*_):
        count.append(1)

    event.listen(engine, "before_cursor_execute", tick)
    try:
        make_machine(db, stage="spinning")
        count.clear()
        board(client)
        one = len(count)
        for _ in range(9):
            make_machine(db, stage="weaving")
        count.clear()
        board(client)
        ten = len(count)
    finally:
        event.remove(engine, "before_cursor_execute", tick)
    assert ten == one
