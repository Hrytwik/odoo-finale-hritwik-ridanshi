"""B2 Task 6: order lifecycle (R3), yarn check, progress and the buyer-facing stage.
Hand-worked numbers: 5,000 m poplin, 0.12 kg/m, 5% wastage -> need 630 kg; issued 587.5 -> outstanding 42.5."""
import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.core.events import broadcaster
from app.db.models import FabricRecipeLine, Order
from tests.factories import (
    dye, make_buyer, make_dispatch, make_fabric_type, make_inspection, make_lot, make_machine, make_order,
    make_roll, make_run, make_yarn_type, put_on_dispatch,
)
from tests.test_stock_views import give_back, issue, scenario, second_order_needing_400, spinning_run

IST = ZoneInfo("Asia/Kolkata")


def today():
    return dt.datetime.now(IST).date()


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


def order_count(db):
    return db.scalar(select(func.count()).select_from(Order))


def new_order_body(db, **over):
    fabric = make_fabric_type(db)
    return {"buyer_id": make_buyer(db).id, "fabric_type_id": fabric.id, "colour": "navy", "qty_metres": 5000,
            "price_per_metre": 120, "deadline": str(today() + dt.timedelta(days=20)), **over}


def get(client, code):
    r = client.get(f"/api/orders/{code}")
    assert r.status_code == 200, r.text
    return r.json()


# ---- create ------------------------------------------------------------------------------

def test_create_makes_a_draft_with_a_code_and_zero_progress(client, db, login_as, events):
    login_as("owner")
    body = new_order_body(db)
    r = client.post("/api/orders", json=body)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["code"].startswith("ORD-") and out["state"] == "draft" and out["stage"] == "draft"
    assert out["colour"] == "navy" and out["qty_metres"] == 5000 and out["price_per_metre"] == 120
    assert out["buyer"]["id"] == body["buyer_id"] and out["fabric_type"]["id"] == body["fabric_type_id"]
    assert out["confirmed_at"] is None and out["delivery_date"] is None and out["days_late"] is None
    assert out["progress"] == {"need_kg": 630.0, "spun_kg": 0, "woven_m": 0, "dyed_m": 0, "passed_m": 0,
                               "rejected_m": 0, "dispatched_m": 0}
    assert events == [("order.changed", out["id"])]


def test_create_rounds_half_up_and_refuses_rounding_to_zero(client, db, login_as):
    login_as("accountant")
    r = client.post("/api/orders", json=new_order_body(db, qty_metres=100.0005, price_per_metre=1.005))
    assert r.status_code == 201 and r.json()["qty_metres"] == 100.001 and r.json()["price_per_metre"] == 1.01
    before = order_count(db)
    for over, field in (({"qty_metres": 0.0004}, "qty_metres"), ({"price_per_metre": 0.004}, "price_per_metre")):
        r = client.post("/api/orders", json=new_order_body(db, **over))
        assert r.status_code == 422 and r.json()["field"] == field
    assert order_count(db) == before


def test_create_deadline_today_is_fine_yesterday_is_not(client, db, login_as, events):
    login_as("owner")
    assert client.post("/api/orders", json=new_order_body(db, deadline=str(today()))).status_code == 201
    events.clear()
    before = order_count(db)
    r = client.post("/api/orders", json=new_order_body(db, deadline=str(today() - dt.timedelta(days=1))))
    assert r.status_code == 422 and r.json()["code"] == "DEADLINE_IN_PAST" and r.json()["field"] == "deadline"
    assert order_count(db) == before and events == []


@pytest.mark.parametrize("over, field", [({"buyer_id": 999999}, "buyer_id"), ({"fabric_type_id": 999999}, "fabric_type_id")])
def test_create_unknown_buyer_or_fabric_is_404(client, db, login_as, events, over, field):
    login_as("owner")
    r = client.post("/api/orders", json=new_order_body(db, **over))
    assert r.status_code == 404 and r.json()["field"] == field and events == []


@pytest.mark.parametrize("over", [{"colour": "  "}, {"qty_metres": 0}, {"qty_metres": -1}, {"price_per_metre": 0},
                                  {"deadline": "not-a-date"}, {"qty_metres": 1e9}])
def test_create_validation(client, db, login_as, over):
    login_as("owner")
    assert client.post("/api/orders", json=new_order_body(db, **over)).status_code == 422


# ---- confirm, cancel, deadline ------------------------------------------------------------

def draft(db, **kw):
    return make_order(db, state="draft", **kw)


def test_confirm_sets_the_time_and_works_even_with_a_yarn_shortage(client, db, login_as, events):
    login_as("owner")
    order = draft(db)      # a fabric with no stock at all: shortage
    r = client.post(f"/api/orders/{order.code}/confirm")
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "confirmed" and r.json()["confirmed_at"] is not None
    assert r.json()["stage"] == "waiting_to_start" and r.json()["yarn_status"] == "short"
    assert events == [("order.changed", order.id), ("stock.changed", None)]


def test_confirm_twice_or_a_cancelled_order_is_refused(client, db, login_as, events):
    login_as("owner")
    order = draft(db)
    client.post(f"/api/orders/{order.code}/confirm")
    events.clear()
    for target in (order, make_order(db, state="cancelled")):
        r = client.post(f"/api/orders/{target.code}/confirm")
        assert r.status_code == 409 and r.json()["code"] == "ORDER_NOT_DRAFT"
    assert events == []


def test_cancel_a_draft_and_a_confirmed_order_without_runs(client, db, login_as, events):
    login_as("owner")
    for order in (draft(db), make_order(db)):
        events.clear()
        r = client.post(f"/api/orders/{order.code}/cancel")
        assert r.status_code == 200 and r.json()["state"] == "cancelled" and r.json()["stage"] == "cancelled"
        assert r.json()["yarn_status"] == "not_needed"
        assert events == [("order.changed", order.id), ("stock.changed", None)]


def test_cancel_refused_when_runs_exist_or_already_cancelled(client, db, login_as, events):
    login_as("owner")
    busy = make_order(db)
    spinning_run(db, busy)
    r = client.post(f"/api/orders/{busy.code}/cancel")
    assert r.status_code == 409 and r.json()["code"] == "ORDER_HAS_RUNS"
    gone = make_order(db, state="cancelled")
    r = client.post(f"/api/orders/{gone.code}/cancel")
    assert r.status_code == 409 and r.json()["code"] == "ORDER_ALREADY_CANCELLED"
    assert client.get(f"/api/orders/{busy.code}").json()["state"] == "confirmed"


def test_cancelling_releases_the_yarn_it_reserved(client, db, login_as):
    login_as("owner")
    cotton, _, order, lot = scenario(db)
    second = second_order_needing_400(db, cotton)
    stock = lambda: client.get("/api/stock").json()  # noqa: E731
    row = next(x for x in stock() if x["yarn_type"]["id"] == cotton.id)
    assert row["outstanding_kg"] == 1030          # 630 + 400
    client.post(f"/api/orders/{second.code}/cancel")
    row = next(x for x in stock() if x["yarn_type"]["id"] == cotton.id)
    assert row["outstanding_kg"] == 630


def test_change_deadline(client, db, login_as, events):
    login_as("accountant")
    order = make_order(db)
    new = today() + dt.timedelta(days=45)
    r = client.patch(f"/api/orders/{order.code}", json={"deadline": str(new)})
    assert r.status_code == 200 and r.json()["deadline"] == str(new) and events == [("order.changed", order.id)]
    assert client.patch(f"/api/orders/{order.code}", json={"deadline": str(today())}).status_code == 200


def test_change_deadline_refusals(client, db, login_as, events):
    login_as("owner")
    order, gone = make_order(db), make_order(db, state="cancelled")
    events.clear()
    r = client.patch(f"/api/orders/{order.code}", json={"deadline": str(today() - dt.timedelta(days=1))})
    assert r.status_code == 422 and r.json()["code"] == "DEADLINE_IN_PAST"
    r = client.patch(f"/api/orders/{gone.code}", json={"deadline": str(today() + dt.timedelta(days=3))})
    assert r.status_code == 409 and r.json()["code"] == "ORDER_CANCELLED"
    assert events == []


def test_unknown_order_is_404_everywhere(client, login_as):
    login_as("owner")
    for method, path, kw in (("get", "", {}), ("post", "/confirm", {}), ("post", "/cancel", {}),
                             ("get", "/yarn-check", {}), ("patch", "", {"json": {"deadline": "2030-01-01"}})):
        r = getattr(client, method)(f"/api/orders/ORD-9999999{path}", **kw)
        assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND", (method, path)


# ---- yarn check and yarn_status (the -230 scenario) ----------------------------------------

def test_yarn_check_with_the_worked_numbers(client, db, login_as):
    login_as("store")
    cotton, _, order, lot = scenario(db)
    issue(db, lot, spinning_run(db, order), 587.5)
    second = second_order_needing_400(db, cotton)
    r = client.get(f"/api/orders/{second.code}/yarn-check")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["order_code"] == second.code and out["can_start"] is False
    [line] = out["lines"]
    assert line["yarn_type"]["id"] == cotton.id
    assert (line["need_kg"], line["issued_kg"], line["outstanding_kg"]) == (400.0, 0.0, 400.0)
    assert line["available_kg"] == 170.0 and line["short_kg"] == 230.0   # 212.5 on hand - 42.5 owed to the first order
    first = client.get(f"/api/orders/{order.code}/yarn-check").json()["lines"][0]
    assert (first["need_kg"], first["issued_kg"], first["outstanding_kg"]) == (630.0, 587.5, 42.5)
    # the other order owes 400 kg against 212.5 on hand, so nothing is free for this one (never shown below 0)
    assert first["available_kg"] == 0.0 and first["short_kg"] == 42.5


def test_yarn_status_and_short_kg_in_the_order(client, db, login_as):
    login_as("owner")
    cotton, _, order, lot = scenario(db)
    issue(db, lot, spinning_run(db, order), 587.5)
    second = second_order_needing_400(db, cotton)
    out = get(client, second.code)
    assert out["yarn_status"] == "short" and out["short_kg"] == 230.0
    assert out["progress"]["need_kg"] == 400.0


def test_enough_yarn_means_can_start(client, db, login_as):
    login_as("owner")
    cotton, _, order, lot = scenario(db)           # 800 kg on hand, need 630
    out = get(client, order.code)
    assert out["yarn_status"] == "can_start" and out["short_kg"] == 0
    assert client.get(f"/api/orders/{order.code}/yarn-check").json()["can_start"] is True


def test_yarn_status_is_not_needed_after_full_issue_and_for_cancelled(client, db, login_as):
    login_as("owner")
    cotton, _, order, lot = scenario(db)
    issue(db, lot, spinning_run(db, order), 630)
    assert get(client, order.code)["yarn_status"] == "not_needed"
    assert get(client, make_order(db, state="cancelled").code)["yarn_status"] == "not_needed"


def test_a_return_raises_outstanding_again(client, db, login_as):
    login_as("owner")
    cotton, _, order, lot = scenario(db)
    run = spinning_run(db, order)
    issue(db, lot, run, 587.5)
    give_back(db, lot, run, 20)
    line = client.get(f"/api/orders/{order.code}/yarn-check").json()["lines"][0]
    assert (line["issued_kg"], line["outstanding_kg"]) == (567.5, 62.5)


def test_draft_and_cancelled_orders_never_reserve_yarn_for_others(client, db, login_as):
    login_as("owner")
    cotton, _, order, lot = scenario(db)
    draft_big = make_order(db, state="draft", fabric_type=order.fabric_type, qty_metres=50000)
    make_order(db, state="cancelled", fabric_type=order.fabric_type, qty_metres=50000)
    line = client.get(f"/api/orders/{order.code}/yarn-check").json()["lines"][0]
    assert line["available_kg"] == 800.0 and line["short_kg"] == 0.0
    # a draft is checked as if it were about to be confirmed: it competes only with CONFIRMED orders (630 of 800 kg)
    line = client.get(f"/api/orders/{draft_big.code}/yarn-check").json()["lines"][0]
    assert line["available_kg"] == 170.0


def test_a_blocked_lot_is_not_available_for_the_check(client, db, login_as):
    login_as("owner")
    cotton, _, order, lot = scenario(db)
    lot.is_blocked, lot.blocked_reason, lot.blocked_at = True, "damp", dt.datetime(2026, 10, 2, tzinfo=dt.UTC)
    db.flush()
    line = client.get(f"/api/orders/{order.code}/yarn-check").json()["lines"][0]
    assert line["available_kg"] == 0.0 and line["short_kg"] == 630.0
    assert get(client, order.code)["yarn_status"] == "short"


def test_a_recipe_with_two_yarns_has_two_lines_and_can_start_only_if_all_are_covered(client, db, login_as):
    login_as("owner")
    warp, weft = make_yarn_type(db), make_yarn_type(db)
    fabric = make_fabric_type(db, yarn_type=warp, kg_per_metre=0.1, wastage_pct=0)
    db.add(FabricRecipeLine(fabric_type_id=fabric.id, yarn_type_id=weft.id, kg_per_metre=0.05))
    db.flush()
    order = make_order(db, fabric_type=fabric, qty_metres=1000)    # warp 100 kg, weft 50 kg
    make_lot(db, yarn_type=warp, qty_kg=100)
    make_lot(db, yarn_type=weft, qty_kg=49)
    out = client.get(f"/api/orders/{order.code}/yarn-check").json()
    assert len(out["lines"]) == 2 and out["can_start"] is False
    shorts = {line["yarn_type"]["id"]: line["short_kg"] for line in out["lines"]}
    assert shorts == {warp.id: 0.0, weft.id: 1.0}
    assert get(client, order.code)["short_kg"] == 1.0


# ---- progress and stage ---------------------------------------------------------------------

class Floor:
    """Builds the production history of one 1,000 m order step by step."""

    def __init__(self, db, qty=1000):
        self.db = db
        self.order = make_order(db, qty_metres=qty)
        self.spin = make_run(db, self.order, make_machine(db, stage="spinning"))
        self.weave = None
        self.dyeing = None

    def spin_done(self, kg=640):
        self.spin.ended_at, self.spin.output_kg = self.spin.started_at, Decimal(str(kg))
        self.db.flush()

    def start_weaving(self):
        self.weave = make_run(self.db, self.order, make_machine(self.db, stage="weaving"), input_run_id=self.spin.id)
        return self.weave

    def roll(self, metres=100):
        return make_roll(self.db, self.order, self.weave, metres)

    def start_dyeing(self):
        self.dyeing = make_run(self.db, self.order, make_machine(self.db, stage="dyeing"))
        return self.dyeing

    def finish_dyeing(self, *rolls):
        for roll in rolls:
            dye(self.db, roll, self.dyeing)
        self.dyeing.ended_at = self.dyeing.started_at
        self.db.flush()


def view(client, order):
    out = client.get(f"/api/orders/{order.code}").json()
    return out["stage"], out["progress"]


def test_stage_walks_from_waiting_to_dispatched(client, db, login_as):
    login_as("owner")
    f = Floor(db, qty=1000)
    db.delete(f.spin)       # start with no runs at all
    db.flush()
    assert view(client, f.order)[0] == "waiting_to_start"

    f.spin = make_run(db, f.order, make_machine(db, stage="spinning"))
    assert view(client, f.order)[0] == "spinning"

    f.spin_done(640)
    f.start_weaving()
    stage, progress = view(client, f.order)
    assert stage == "weaving" and progress["spun_kg"] == 640.0

    rolls = [f.roll(500), f.roll(500)]
    f.start_dyeing()
    stage, progress = view(client, f.order)
    assert stage == "dyeing" and progress["woven_m"] == 1000.0 and progress["dyed_m"] == 0

    f.finish_dyeing(*rolls)
    stage, progress = view(client, f.order)
    assert stage == "quality_check" and progress["dyed_m"] == 1000.0       # dyed, not yet inspected

    make_inspection(db, rolls[0], "pass")
    stage, progress = view(client, f.order)
    assert stage == "quality_check" and progress["passed_m"] == 500.0      # the other roll is still waiting

    make_inspection(db, rolls[1], "pass")
    stage, progress = view(client, f.order)
    assert stage == "ready_to_ship" and progress["passed_m"] == 1000.0

    loading = make_dispatch(db, f.order.buyer)
    put_on_dispatch(db, rolls[0], loading)
    assert view(client, f.order)[0] == "ready_to_ship"                      # still loading: nothing has left

    loading.state, loading.dispatched_at = "dispatched", dt.datetime(2026, 10, 9, tzinfo=dt.UTC)
    db.flush()
    stage, progress = view(client, f.order)
    assert stage == "partly_dispatched" and progress["dispatched_m"] == 500.0

    second = make_dispatch(db, f.order.buyer, state="dispatched", dispatched_at=dt.datetime(2026, 10, 10, tzinfo=dt.UTC))
    put_on_dispatch(db, rolls[1], second)
    stage, progress = view(client, f.order)
    assert stage == "dispatched" and progress["dispatched_m"] == 1000.0


def test_latest_verdict_wins_reject_then_a_later_pass(client, db, login_as):
    login_as("owner")
    f = Floor(db, qty=100)
    f.spin_done()
    f.start_weaving()
    roll = f.roll(100)
    f.start_dyeing()
    f.finish_dyeing(roll)
    make_inspection(db, roll, "reject", inspected_at=dt.datetime(2026, 10, 9, tzinfo=dt.UTC))
    stage, progress = view(client, f.order)
    assert progress["rejected_m"] == 100.0 and progress["passed_m"] == 0 and stage != "ready_to_ship"
    make_inspection(db, roll, "pass", inspected_at=dt.datetime(2026, 10, 10, tzinfo=dt.UTC))
    stage, progress = view(client, f.order)
    assert progress["rejected_m"] == 0 and progress["passed_m"] == 100.0 and stage == "ready_to_ship"


def test_latest_verdict_wins_pass_then_a_later_rework(client, db, login_as):
    login_as("owner")
    f = Floor(db, qty=100)
    f.spin_done()
    f.start_weaving()
    roll = f.roll(100)
    f.start_dyeing()
    f.finish_dyeing(roll)
    make_inspection(db, roll, "pass", inspected_at=dt.datetime(2026, 10, 9, tzinfo=dt.UTC))
    assert view(client, f.order)[0] == "ready_to_ship"
    make_inspection(db, roll, "rework", inspected_at=dt.datetime(2026, 10, 10, tzinfo=dt.UTC))
    stage, progress = view(client, f.order)
    assert stage == "quality_check" and progress["passed_m"] == 0 and progress["rejected_m"] == 0


def test_an_order_whose_rolls_are_all_rejected_never_gets_ready_to_ship(client, db, login_as):
    login_as("owner")
    f = Floor(db, qty=200)
    f.spin_done()
    f.start_weaving()
    rolls = [f.roll(100), f.roll(100)]
    f.start_dyeing()
    f.finish_dyeing(*rolls)
    for roll in rolls:
        make_inspection(db, roll, "reject")
    stage, progress = view(client, f.order)
    assert progress["rejected_m"] == 200.0 and progress["passed_m"] == 0
    assert stage == "dyeing"       # nothing left to inspect, nothing to ship: the furthest stage still reached


def test_a_loading_dispatch_is_not_dispatched_metres(client, db, login_as):
    login_as("owner")
    f = Floor(db, qty=100)
    f.spin_done()
    f.start_weaving()
    roll = f.roll(100)
    make_inspection(db, roll, "pass")
    put_on_dispatch(db, roll, make_dispatch(db, f.order.buyer))        # state defaults to loading
    assert view(client, f.order)[1]["dispatched_m"] == 0


def test_a_roll_counts_once_even_with_two_dye_links(client, db, login_as):
    login_as("owner")
    f = Floor(db, qty=100)
    f.spin_done()
    f.start_weaving()
    roll = f.roll(100)
    f.start_dyeing()
    f.finish_dyeing(roll)
    again = make_run(db, f.order, make_machine(db, stage="dyeing"))
    dye(db, roll, again)
    again.ended_at = again.started_at
    db.flush()
    assert view(client, f.order)[1]["dyed_m"] == 100.0


def test_progress_ignores_other_orders(client, db, login_as):
    login_as("owner")
    f, other = Floor(db, qty=100), Floor(db, qty=100)
    for floor in (f, other):
        floor.spin_done(100)
        floor.start_weaving()
        floor.roll(100)
    assert view(client, f.order)[1]["spun_kg"] == 100.0 and view(client, f.order)[1]["woven_m"] == 100.0


# ---- list, roles ------------------------------------------------------------------------------

def test_list_filters_and_order(client, db, login_as):
    login_as("supervisor")
    buyer_a, buyer_b = make_buyer(db), make_buyer(db)
    a1 = make_order(db, buyer=buyer_a)
    a2 = make_order(db, buyer=buyer_a, state="draft")
    b1 = make_order(db, buyer=buyer_b, state="cancelled")
    codes = lambda url: [o["code"] for o in client.get(url).json()]  # noqa: E731
    assert codes(f"/api/orders?buyer_id={buyer_a.id}") == [a2.code, a1.code]          # newest first
    assert codes(f"/api/orders?buyer_id={buyer_a.id}&state=draft") == [a2.code]
    assert codes(f"/api/orders?state=cancelled") == [b1.code]
    r = client.get("/api/orders?state=whatever")
    assert r.status_code == 422 and r.json()["field"] == "state"


@pytest.mark.parametrize("role, can_read", [("owner", True), ("accountant", True), ("supervisor", True), ("store", True),
                                            ("qc", False), ("dispatch", False), ("buyer", False)])
def test_who_can_read_orders(client, db, login_as, role, can_read):
    login_as(role)
    make_order(db)
    assert (client.get("/api/orders").status_code == 200) is can_read


@pytest.mark.parametrize("role, can", [("owner", True), ("accountant", True), ("store", False), ("supervisor", False),
                                       ("qc", False), ("dispatch", False), ("buyer", False)])
def test_who_can_write_orders(client, db, login_as, role, can):
    login_as(role)
    order = make_order(db, state="draft")
    assert (client.post("/api/orders", json=new_order_body(db)).status_code == 201) is can
    assert (client.post(f"/api/orders/{order.code}/confirm").status_code == 200) is can
    assert (client.patch(f"/api/orders/{order.code}", json={"deadline": str(today() + dt.timedelta(days=9))}
                         ).status_code == 200) is can
    assert (client.post(f"/api/orders/{order.code}/cancel").status_code == 200) is can


# ---- two requests on one order ------------------------------------------------------------------

def test_a_confirm_waits_for_whoever_holds_the_orders_lock_and_then_sees_their_result(engine):
    """Session A holds the order's row lock and cancels it; B's confirm must wait, then be refused (not a draft any more)."""
    import threading
    import time

    from sqlalchemy.orm import Session

    from app.core.errors import AppError
    from app.modules.orders import service
    from tests.helpers import wipe_database

    with Session(engine) as setup:
        code = make_order(setup, state="draft").code
        setup.commit()
    outcome: list[object] = []

    def confirm():
        with Session(engine) as session:
            try:
                service.confirm_order(session, code)
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            order = service.get_order_or_404(holder, code, for_update=True)
            thread = threading.Thread(target=confirm)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "the confirm must be waiting on the lock"
            order.state = "cancelled"
            holder.commit()
            thread.join(timeout=10)
        assert outcome == ["ORDER_NOT_DRAFT"]
        with Session(engine) as check:
            assert check.scalar(select(Order.state).where(Order.code == code)) == "cancelled"
    finally:
        wipe_database(engine)
