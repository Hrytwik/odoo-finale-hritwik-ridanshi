"""B2 Task 5: issue, return, adjust (R2, R2b) and block lot (R14).
Hand-worked numbers: lot 800 kg; issue 587.5 -> on hand 212.5; return 20 -> 232.5 (issued 567.5)."""
import datetime as dt
import threading
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import ProductionRun, User, YarnLot, YarnMovement, YarnType
from app.modules.store import schemas as s
from app.modules.store import service
from tests.factories import make_lot, make_machine, make_order, make_run, make_user, make_yarn_type
from tests.helpers import wipe_database
from tests.test_stock_views import give_back, issue, scenario, spinning_run


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


@pytest.fixture
def world(db):
    cotton, fabric, order, lot = scenario(db)
    return {"cotton": cotton, "order": order, "lot": lot, "run": spinning_run(db, order)}


def on_hand(db, lot) -> Decimal:
    return db.execute(text("SELECT on_hand_kg FROM v_lot_stock WHERE yarn_lot_id = :i"), {"i": lot.id}).scalar_one()


def ledger_rows(db) -> int:
    return db.scalar(select(func.count()).select_from(YarnMovement))


def post_issue(client, world, qty, **over):
    return client.post("/api/movements/issue", json={
        "lot_code": world["lot"].lot_code, "run_id": world["run"].id, "qty_kg": qty, **over})


def post_return(client, world, qty, **over):
    return client.post("/api/movements/return", json={
        "lot_code": world["lot"].lot_code, "run_id": world["run"].id, "qty_kg": qty, **over})


# ---- the worked numbers -------------------------------------------------------------------

def test_issue_587_5_then_return_20(client, db, login_as, world, events):
    user = login_as("supervisor")
    r = post_issue(client, world, 587.5)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["kind"] == "issue" and out["qty_kg"] == -587.5 and out["lot_code"] == world["lot"].lot_code
    assert out["run_id"] == world["run"].id and out["order_code"] == world["order"].code
    assert out["machine_code"] == world["run"].machine.code and out["by"] == user.username
    assert on_hand(db, world["lot"]) == Decimal("212.500")
    r = post_return(client, world, 20)
    assert r.status_code == 201 and r.json()["kind"] == "return" and r.json()["qty_kg"] == 20
    assert on_hand(db, world["lot"]) == Decimal("232.500")
    assert [k for k, _ in events] == ["lot.changed", "stock.changed"] * 2


def test_issue_exactly_equal_to_on_hand_succeeds_and_one_gram_more_fails(client, db, login_as, world):
    login_as("store")
    assert post_issue(client, world, 800.001).status_code == 409
    assert post_issue(client, world, 800).status_code == 201
    assert on_hand(db, world["lot"]) == 0
    r = post_issue(client, world, 0.001)
    assert r.status_code == 409 and r.json()["code"] == "INSUFFICIENT_STOCK" and r.json()["field"] == "qty_kg"


def test_insufficient_stock_says_how_much_is_available(client, login_as, world):
    login_as("store")
    post_issue(client, world, 587.5)
    r = post_issue(client, world, 300)
    assert r.status_code == 409 and "212.5" in r.json()["message"]


# ---- every refusal leaves the ledger alone and publishes nothing ---------------------------

def refused(client, db, events, response, status, code, field):
    before = ledger_rows(db)
    assert response.status_code == status, response.text
    assert response.json()["code"] == code and response.json()["field"] == field
    assert ledger_rows(db) == before and events == []


def test_unknown_lot_and_run_are_404(client, db, login_as, world, events):
    login_as("store")
    before = ledger_rows(db)
    r = client.post("/api/movements/issue", json={"lot_code": "L-9999999", "run_id": world["run"].id, "qty_kg": 5})
    refused(client, db, events, r, 404, "NOT_FOUND", "lot_code")
    r = client.post("/api/movements/issue", json={"lot_code": world["lot"].lot_code, "run_id": 99999999, "qty_kg": 5})
    refused(client, db, events, r, 404, "NOT_FOUND", "run_id")
    r = client.post("/api/movements/return", json={"lot_code": world["lot"].lot_code, "run_id": 99999999, "qty_kg": 5})
    refused(client, db, events, r, 404, "NOT_FOUND", "run_id")
    assert ledger_rows(db) == before


def test_issuing_from_a_blocked_lot_is_refused(client, db, login_as, world, events):
    login_as("store")
    assert client.post(f"/api/lots/{world['lot'].lot_code}/block", json={"reason": "damp"}).status_code == 200
    events.clear()
    refused(client, db, events, post_issue(client, world, 5), 409, "LOT_BLOCKED", "lot_code")


def test_issuing_to_a_run_that_is_not_open_spinning_of_a_confirmed_order_is_refused(client, db, login_as, world, events):
    login_as("store")
    closed = spinning_run(db, world["order"])
    closed.ended_at = closed.started_at
    weaving = make_run(db, world["order"], make_machine(db, stage="weaving"))
    draft = make_order(db, fabric_type=world["order"].fabric_type, state="draft")
    cancelled = make_order(db, fabric_type=world["order"].fabric_type, state="cancelled")
    db.flush()
    for run in (closed, weaving, spinning_run(db, draft), spinning_run(db, cancelled)):
        refused(client, db, events, post_issue(client, world, 5, run_id=run.id), 409, "RUN_NOT_OPEN", "run_id")


def test_yarn_that_is_not_in_the_orders_recipe_is_refused(client, db, login_as, world, events):
    login_as("store")
    other_lot = make_lot(db, yarn_type=make_yarn_type(db), qty_kg=100)
    refused(client, db, events, post_issue(client, world, 5, lot_code=other_lot.lot_code), 409,
            "YARN_NOT_IN_RECIPE", "lot_code")


@pytest.mark.parametrize("qty", ["0.0004", "0", "-5", "NaN", "true", "1e9"])
def test_bad_issue_quantities_are_a_422_on_qty_kg(client, db, login_as, world, events, qty):
    login_as("store")
    raw = '{"lot_code": "%s", "run_id": %d, "qty_kg": %s}' % (world["lot"].lot_code, world["run"].id, qty)
    before = ledger_rows(db)
    r = client.post("/api/movements/issue", content=raw, headers={"content-type": "application/json"})
    assert r.status_code == 422 and "qty_kg" in (r.json().get("fields") or {r.json()["field"]: ""})
    assert ledger_rows(db) == before and events == []


# ---- returns -----------------------------------------------------------------------------

def test_cannot_return_more_than_was_issued_net_of_earlier_returns(client, db, login_as, world, events):
    login_as("store")
    post_issue(client, world, 100)
    post_return(client, world, 60)
    events.clear()
    refused(client, db, events, post_return(client, world, 40.001), 409, "RETURN_EXCEEDS_ISSUED", "qty_kg")
    assert post_return(client, world, 40).status_code == 201
    events.clear()
    refused(client, db, events, post_return(client, world, 0.001), 409, "RETURN_EXCEEDS_ISSUED", "qty_kg")


def test_cannot_return_to_a_run_that_was_never_given_this_lot(client, db, login_as, world, events):
    login_as("store")
    post_issue(client, world, 100)
    elsewhere = spinning_run(db, world["order"])
    events.clear()
    refused(client, db, events, post_return(client, world, 10, run_id=elsewhere.id), 409,
            "RETURN_EXCEEDS_ISSUED", "qty_kg")
    other_lot = make_lot(db, yarn_type=world["cotton"], qty_kg=100)
    refused(client, db, events, post_return(client, world, 10, lot_code=other_lot.lot_code), 409,
            "RETURN_EXCEEDS_ISSUED", "qty_kg")


def test_a_return_is_allowed_on_a_closed_run_and_on_a_blocked_lot(client, db, login_as, world):
    login_as("store")
    post_issue(client, world, 100)
    world["run"].ended_at = world["run"].started_at
    db.flush()
    assert client.post(f"/api/lots/{world['lot'].lot_code}/block", json={"reason": "damp"}).status_code == 200
    assert post_return(client, world, 30).status_code == 201
    assert on_hand(db, world["lot"]) == Decimal("730.000")


# ---- adjustments -------------------------------------------------------------------------

def adjust(client, lot, qty, note="stock count"):
    return client.post("/api/movements/adjust", json={"lot_code": lot.lot_code, "qty_kg": qty, "note": note})


def test_adjust_up_and_down_within_stock(client, db, login_as, world, events):
    login_as("store")
    r = adjust(client, world["lot"], 12.5)
    assert r.status_code == 201 and r.json()["kind"] == "adjustment" and r.json()["note"] == "stock count"
    assert r.json()["qty_kg"] == 12.5 and r.json()["run_id"] is None
    assert adjust(client, world["lot"], -812.5).status_code == 201
    assert on_hand(db, world["lot"]) == 0
    assert [k for k, _ in events] == ["lot.changed", "stock.changed"] * 2


def test_a_negative_adjustment_cannot_exceed_on_hand(client, db, login_as, world, events):
    login_as("store")
    refused(client, db, events, adjust(client, world["lot"], -800.001), 409, "INSUFFICIENT_STOCK", "qty_kg")


def test_adjust_on_a_blocked_lot_is_allowed(client, db, login_as, world):
    login_as("store")
    client.post(f"/api/lots/{world['lot'].lot_code}/block", json={"reason": "damp"})
    assert adjust(client, world["lot"], -10).status_code == 201


@pytest.mark.parametrize("qty, note", [(0.0004, "x"), (0, "x"), (5, "  "), (-0.0004, "x")])
def test_bad_adjustments_are_a_422(client, db, login_as, world, events, qty, note):
    login_as("store")
    before = ledger_rows(db)
    r = adjust(client, world["lot"], qty, note)
    assert r.status_code == 422 and ledger_rows(db) == before and events == []


@pytest.mark.parametrize("qty", ["NaN", "Infinity", "-Infinity", "true", '"abc"', "null", "1e9", "-1e9"])
def test_adjust_refuses_non_numbers_and_huge_values(client, db, login_as, world, events, qty):
    login_as("store")
    raw = '{"lot_code": "%s", "qty_kg": %s, "note": "count"}' % (world["lot"].lot_code, qty)
    before = ledger_rows(db)
    r = client.post("/api/movements/adjust", content=raw, headers={"content-type": "application/json"})
    assert r.status_code == 422 and ledger_rows(db) == before and events == []


def test_adjust_unknown_lot_is_404(client, login_as):
    login_as("store")
    r = client.post("/api/movements/adjust", json={"lot_code": "L-9999999", "qty_kg": 5, "note": "x"})
    assert r.status_code == 404 and r.json()["field"] == "lot_code"


# ---- blocking ----------------------------------------------------------------------------

def test_block_marks_the_lot_removes_its_stock_and_cannot_repeat(client, db, login_as, world, events):
    login_as("store")
    before = dt.datetime.now(dt.UTC)
    r = client.post(f"/api/lots/{world['lot'].lot_code}/block", json={"reason": "  damp  "})
    assert r.status_code == 200, r.text
    assert r.json()["is_blocked"] is True and r.json()["blocked_reason"] == "damp" and r.json()["on_hand_kg"] == 800
    lot = db.scalar(select(YarnLot).where(YarnLot.id == world["lot"].id))
    db.refresh(lot)
    assert lot.blocked_at is not None and lot.blocked_at >= before - dt.timedelta(seconds=5)
    stock = db.execute(text("SELECT on_hand_kg FROM v_yarn_type_stock WHERE yarn_type_id = :y"),
                       {"y": world["cotton"].id}).scalar_one()
    assert stock == 0
    assert [k for k, _ in events] == ["lot.changed", "stock.changed"]
    events.clear()
    refused(client, db, events, client.post(f"/api/lots/{lot.lot_code}/block", json={"reason": "again"}), 409,
            "LOT_ALREADY_BLOCKED", "lot_code")


def test_block_validates_and_404s(client, login_as, world):
    login_as("store")
    assert client.post("/api/lots/L-9999999/block", json={"reason": "x"}).status_code == 404
    assert client.post(f"/api/lots/{world['lot'].lot_code}/block", json={"reason": "  "}).status_code == 422


# ---- roles -------------------------------------------------------------------------------

@pytest.mark.parametrize("role, can", [("store", True), ("supervisor", True), ("owner", True),
                                       ("accountant", False), ("qc", False), ("dispatch", False), ("buyer", False)])
def test_issue_and_return_roles(client, login_as, world, role, can):
    login_as(role)
    assert (post_issue(client, world, 5).status_code == 201) is can
    assert (client.post("/api/movements/return", json={"lot_code": world["lot"].lot_code, "run_id": world["run"].id,
                                                       "qty_kg": 1}).status_code != 403) is can


@pytest.mark.parametrize("role, can", [("store", True), ("owner", True), ("supervisor", False), ("accountant", False),
                                       ("qc", False), ("dispatch", False), ("buyer", False)])
def test_adjust_and_block_roles(client, login_as, world, role, can):
    login_as(role)
    assert (adjust(client, world["lot"], 1).status_code == 201) is can
    assert (client.post(f"/api/lots/{world['lot'].lot_code}/block", json={"reason": "x"}).status_code == 200) is can


# ---- two requests at the same moment (real, separate database sessions) --------------------

def committed_world(engine):
    """Real committed rows (not rolled back) so two threads can fight over them."""
    with Session(engine) as setup:
        cotton, fabric, order, _ = scenario(setup)
        run = spinning_run(setup, order)
        user = make_user(setup, role="store")
        setup.commit()
        return {"cotton_id": cotton.id, "run_id": run.id, "user_id": user.id}


def fight(engine, w, lot_code, action, qty, n=2):
    barrier = threading.Barrier(n)
    results: list[object] = []

    def go():
        with Session(engine) as session:
            actor = session.get(User, w["user_id"])
            body = s.IssueIn(lot_code=lot_code, run_id=w["run_id"], qty_kg=qty)
            barrier.wait()
            try:
                action(session, actor, body)
                results.append("ok")
            except AppError as exc:
                results.append(exc.code)

    threads = [threading.Thread(target=go) for _ in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return sorted(results)


def test_two_simultaneous_issues_against_the_last_kilos_one_wins(engine):
    """Review Focus 1: 300 kg each from a 500 kg lot, five times over fresh lots; never negative stock."""
    w = committed_world(engine)
    try:
        for _ in range(5):
            with Session(engine) as setup:
                lot = make_lot(setup, yarn_type=setup.get(YarnType, w["cotton_id"]), qty_kg=500)
                setup.commit()
                code, lot_id = lot.lot_code, lot.id
            assert fight(engine, w, code, service.issue_yarn, 300) == ["INSUFFICIENT_STOCK", "ok"]
            with Session(engine) as check:
                assert check.execute(text("SELECT on_hand_kg FROM v_lot_stock WHERE yarn_lot_id=:i"),
                                     {"i": lot_id}).scalar_one() == Decimal("200.000")
    finally:
        wipe_database(engine)


def test_two_simultaneous_returns_cannot_return_more_than_was_issued(engine):
    w = committed_world(engine)
    try:
        with Session(engine) as setup:
            lot = make_lot(setup, yarn_type=setup.get(YarnType, w["cotton_id"]), qty_kg=500)
            issue(setup, lot, setup.get(ProductionRun, w["run_id"]), 400)
            setup.commit()
            code, lot_id = lot.lot_code, lot.id
        assert fight(engine, w, code, service.return_yarn, 300) == ["RETURN_EXCEEDS_ISSUED", "ok"]
        with Session(engine) as check:
            assert check.execute(text("SELECT on_hand_kg FROM v_lot_stock WHERE yarn_lot_id=:i"),
                                 {"i": lot_id}).scalar_one() == Decimal("400.000")  # 500 - 400 + 300
    finally:
        wipe_database(engine)


def test_a_request_waits_for_whoever_holds_the_lots_lock_and_then_sees_their_result(engine):
    """Deterministic version of 'issue and negative adjustment at the same moment': session A holds the lot's row lock
    and spends 300 of 500 kg; B's adjustment of -300 must wait for A to commit and then be refused (200 left)."""
    import time

    w = committed_world(engine)
    try:
        with Session(engine) as setup:
            lot = make_lot(setup, yarn_type=setup.get(YarnType, w["cotton_id"]), qty_kg=500)
            setup.commit()
            code, lot_id = lot.lot_code, lot.id
        outcome: list[object] = []

        def adjust_it():
            with Session(engine) as session:
                actor = session.get(User, w["user_id"])
                try:
                    service.adjust_stock(session, actor, s.AdjustIn(lot_code=code, qty_kg=-300, note="count"))
                    outcome.append("ok")
                except AppError as exc:
                    outcome.append(exc.code)

        with Session(engine) as holder:
            service.get_lot_or_404(holder, code, for_update=True)          # A takes the lock and keeps it
            thread = threading.Thread(target=adjust_it)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "B must be waiting on A's lock"
            holder.add(YarnMovement(yarn_lot_id=lot_id, kind="issue", qty_kg=Decimal("-300"),
                                    production_run_id=w["run_id"], moved_by=w["user_id"]))
            holder.commit()                                                 # A done; B may now look at the ledger
            thread.join(timeout=10)
        assert outcome == ["INSUFFICIENT_STOCK"]
        with Session(engine) as check:
            assert check.execute(text("SELECT on_hand_kg FROM v_lot_stock WHERE yarn_lot_id=:i"),
                                 {"i": lot_id}).scalar_one() == Decimal("200.000")
    finally:
        wipe_database(engine)
