"""B3 Task 6: roll off (R7), load rolls into dyeing (R8) and the real GET /rolls."""
import threading
import time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import Roll, RollRun
from app.modules.floor import rolls as floor_rolls
from app.modules.floor import schemas as s
from app.modules.floor import service
from tests.factories import (
    dye, make_inspection, make_machine, make_order, make_roll, make_run, make_worker,
)
from tests.helpers import wipe_database


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


@pytest.fixture
def sup(login_as):
    return login_as("supervisor")


def roll_count(db) -> int:
    return db.scalar(select(func.count()).select_from(Roll))


def links(db, roll) -> list[str]:
    return [f"{p}" for (p,) in db.execute(select(RollRun.purpose).where(RollRun.roll_id == roll.id))]


def roll_off(client, run, metres):
    return client.post(f"/api/runs/{run.id}/rolls", json={"metres": metres})


def load(client, run, *codes):
    return client.post(f"/api/runs/{run.id}/load-rolls", json={"roll_codes": list(codes)})


def post_raw(client, path, raw):
    return client.post(path, content=raw, headers={"content-type": "application/json"})


def status_of(client, roll):
    return next(r["status"] for r in client.get(f"/api/rolls?order_code={roll.order.code}").json() if r["code"] == roll.code)


class Shop:
    def __init__(self, db):
        self.db = db
        self.order = make_order(db, qty_metres=500)
        self.weave = make_run(db, self.order, make_machine(db, stage="weaving"))
        self.dye = make_run(db, self.order, make_machine(db, stage="dyeing"))


@pytest.fixture
def shop(db):
    return Shop(db)


# ---- roll off ---------------------------------------------------------------------------------

def test_roll_off_makes_a_woven_roll_linked_to_the_run(client, db, sup, shop, events):
    r = roll_off(client, shop.weave, 110)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["code"].startswith("R-") and out["order_code"] == shop.order.code and out["metres"] == 110.0
    assert out["status"] == "woven" and out["colour"] == "navy" and out["created_at"]
    assert out["buyer_name"] == shop.order.buyer.name and out["fabric"] == shop.order.fabric_type.name
    roll = db.scalar(select(Roll).where(Roll.code == out["code"]))
    assert roll.order_id == shop.order.id and links(db, roll) == ["produce"]
    assert events == [("roll.changed", roll.id), ("run.changed", shop.weave.id)]


def test_roll_codes_are_unique_and_increasing(client, db, sup, shop):
    a, b = roll_off(client, shop.weave, 10).json()["code"], roll_off(client, shop.weave, 10).json()["code"]
    assert a != b


def test_a_roll_may_exceed_the_ordered_quantity(client, db, sup, shop):
    assert roll_off(client, shop.weave, 5000).status_code == 201          # the order is 500 m


def test_metres_round_half_up_to_three_places(client, db, sup, shop):
    assert roll_off(client, shop.weave, 1.0005).json()["metres"] == 1.001


@pytest.mark.parametrize("value", ["0", "0.0004", "-1", "NaN", "Infinity", "true", '"abc"', "1e9", "null"])
def test_bad_metres_are_422_on_metres_and_create_nothing(client, db, sup, shop, events, value):
    before = roll_count(db)
    r = post_raw(client, f"/api/runs/{shop.weave.id}/rolls", '{"metres": %s}' % value)
    assert r.status_code == 422 and "metres" in (r.json().get("fields") or {r.json()["field"]: ""})
    assert roll_count(db) == before and events == []


def test_roll_off_needs_an_open_weaving_run(client, db, sup, shop, events):
    spin = make_run(db, shop.order, make_machine(db, stage="spinning"))
    before = roll_count(db)
    for run in (spin, shop.dye):
        r = roll_off(client, run, 10)
        assert r.status_code == 409 and r.json()["code"] == "WRONG_STAGE" and r.json()["field"] == "run_id"
    shop.weave.ended_at = shop.weave.started_at
    db.flush()
    r = roll_off(client, shop.weave, 10)
    assert r.status_code == 409 and r.json()["code"] == "RUN_NOT_OPEN"
    assert client.post("/api/runs/99999999/rolls", json={"metres": 5}).status_code == 404
    assert roll_count(db) == before and events == []


@pytest.mark.parametrize("role, ok", [("supervisor", True), ("owner", True), ("accountant", False), ("store", False),
                                      ("qc", False), ("dispatch", False), ("buyer", False)])
def test_who_can_roll_off_and_load(client, db, login_as, shop, role, ok):
    login_as(role)
    assert (roll_off(client, shop.weave, 10).status_code == 201) is ok
    roll = make_roll(db, shop.order, shop.weave)
    assert (load(client, shop.dye, roll.code).status_code == 200) is ok


# ---- load rolls --------------------------------------------------------------------------------

def test_loading_woven_rolls_into_a_dyeing_run(client, db, sup, shop, events):
    a, b = make_roll(db, shop.order, shop.weave, 100), make_roll(db, shop.order, shop.weave, 120)
    r = load(client, shop.dye, b.code, a.code)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["id"] == shop.dye.id and out["stage"] == "dyeing" and out["roll_codes"] == [a.code, b.code]
    assert out["metres"] == 220.0
    assert sorted(links(db, a)) == ["dye", "produce"]
    assert status_of(client, a) == "dyeing" and status_of(client, b) == "dyeing"
    assert events == [("roll.changed", a.id), ("roll.changed", b.id), ("run.changed", shop.dye.id)]


def bad_roll_untouched(client, db, shop, good, response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["code"] == code and response.json()["field"] == "roll_codes", response.json()
    assert status_of(client, good) == "woven" and "dye" not in links(db, good)


def test_a_roll_already_in_a_dye_run_is_refused_and_nothing_is_loaded(client, db, sup, shop, events):
    good, taken = make_roll(db, shop.order, shop.weave), make_roll(db, shop.order, shop.weave)
    other = make_run(db, shop.order, make_machine(db, stage="dyeing"))
    dye(db, taken, other)
    events.clear()
    r = load(client, shop.dye, good.code, taken.code)
    bad_roll_untouched(client, db, shop, good, r, 409, "ROLL_WRONG_STATUS")
    assert taken.code in r.json()["message"] and events == []


def test_an_inspected_roll_is_refused(client, db, sup, shop):
    good, inspected = make_roll(db, shop.order, shop.weave), make_roll(db, shop.order, shop.weave)
    make_inspection(db, inspected, "pass")
    bad_roll_untouched(client, db, shop, good, load(client, shop.dye, good.code, inspected.code), 409,
                       "ROLL_WRONG_STATUS")


def test_a_roll_of_another_order_is_refused(client, db, sup, shop):
    good = make_roll(db, shop.order, shop.weave)
    foreign_order = make_order(db)
    foreign = make_roll(db, foreign_order, make_run(db, foreign_order, make_machine(db, stage="weaving")))
    r = load(client, shop.dye, good.code, foreign.code)
    bad_roll_untouched(client, db, shop, good, r, 409, "ROLL_WRONG_ORDER")
    assert foreign.code in r.json()["message"]


def test_an_unknown_roll_code_is_404_and_a_duplicate_is_422(client, db, sup, shop):
    good = make_roll(db, shop.order, shop.weave)
    r = load(client, shop.dye, good.code, "R-9999999")
    bad_roll_untouched(client, db, shop, good, r, 404, "NOT_FOUND")
    r = load(client, shop.dye, good.code, good.code)
    bad_roll_untouched(client, db, shop, good, r, 422, "VALIDATION_ERROR")
    assert client.post(f"/api/runs/{shop.dye.id}/load-rolls", json={"roll_codes": []}).status_code == 422


def test_loading_needs_an_open_dyeing_run(client, db, sup, shop, events):
    roll = make_roll(db, shop.order, shop.weave)
    for run in (shop.weave, make_run(db, shop.order, make_machine(db, stage="spinning"))):
        r = load(client, run, roll.code)
        assert r.status_code == 409 and r.json()["code"] == "WRONG_STAGE" and r.json()["field"] == "run_id"
    shop.dye.ended_at = shop.dye.started_at
    db.flush()
    r = load(client, shop.dye, roll.code)
    assert r.status_code == 409 and r.json()["code"] == "RUN_NOT_OPEN"
    assert client.post("/api/runs/99999999/load-rolls", json={"roll_codes": ["R-1"]}).status_code == 404
    assert status_of(client, roll) == "woven" and events == []


# ---- GET /rolls --------------------------------------------------------------------------------

def test_roll_list_filters_status_and_order_and_is_newest_first(client, db, login_as, shop):
    login_as("dispatch")
    other_order = make_order(db)
    other = make_roll(db, other_order, make_run(db, other_order, make_machine(db, stage="weaving")))
    a, b, c = (make_roll(db, shop.order, shop.weave, m) for m in (100, 120, 80))
    dye(db, b, shop.dye)
    make_inspection(db, c, "pass")
    codes = lambda url: [r["code"] for r in client.get(url).json()]  # noqa: E731
    assert codes(f"/api/rolls?order_code={shop.order.code}") == [c.code, b.code, a.code]
    assert codes(f"/api/rolls?order_code={shop.order.code}&status=woven") == [a.code]
    assert codes(f"/api/rolls?order_code={shop.order.code}&status=dyeing") == [b.code]
    assert codes(f"/api/rolls?order_code={shop.order.code}&status=in_store") == [c.code]
    assert codes(f"/api/rolls?order_code={other_order.code}") == [other.code]
    assert codes("/api/rolls?order_code=ORD-9999999") == []
    assert client.get("/api/rolls?status=sleeping").status_code == 422


def test_roll_list_roles(client, db, login_as, shop):
    for role in ("owner", "accountant", "supervisor", "store", "qc", "dispatch"):
        login_as(role)
        assert client.get("/api/rolls").status_code == 200, role
    login_as("buyer")
    assert client.get("/api/rolls").status_code == 403


# ---- two requests at the same moment ----------------------------------------------------------------

def committed_shop(engine, rolls=1):
    with Session(engine) as setup:
        order = make_order(setup, qty_metres=1000)
        weave = make_run(setup, order, make_machine(setup, stage="weaving"))
        made = [make_roll(setup, order, weave) for _ in range(rolls)]
        dye_runs = [make_run(setup, order, make_machine(setup, stage="dyeing")) for _ in range(2)]
        setup.commit()
        return weave.id, [r.code for r in made], [d.id for d in dye_runs]


def test_a_roll_off_waits_for_an_end_on_the_same_run_and_is_then_refused(engine):
    """Review Focus 4: a roll must never attach to a run that has just ended."""
    weave_id, _, _ = committed_shop(engine, rolls=0)
    outcome: list[str] = []

    def roll_it():
        with Session(engine) as session:
            try:
                floor_rolls.roll_off(session, weave_id, s.RollOffIn(metres=10))
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            held = service.locked_open_run(holder, weave_id)
            thread = threading.Thread(target=roll_it)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "the roll-off must be waiting on the run lock"
            held.ended_at = service.db_now(holder)
            holder.commit()
            thread.join(timeout=10)
        assert outcome == ["RUN_NOT_OPEN"]
        with Session(engine) as check:
            assert check.scalar(select(func.count()).select_from(Roll)) == 0
    finally:
        wipe_database(engine)


def test_two_dyeing_runs_cannot_both_load_the_same_roll_while_one_holds_the_roll_locks(engine):
    _, codes, (dye_a, dye_b) = committed_shop(engine)
    outcome: list[str] = []

    def load_b():
        with Session(engine) as session:
            try:
                floor_rolls.load_rolls(session, dye_b, s.LoadRollsIn(roll_codes=codes))
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            service.locked_open_run(holder, dye_a, stage="dyeing")
            roll = holder.scalar(select(Roll).where(Roll.code == codes[0]).with_for_update())
            thread = threading.Thread(target=load_b)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "the second load must be waiting on the roll lock"
            holder.add(RollRun(roll_id=roll.id, run_id=dye_a, purpose="dye"))
            holder.commit()
            thread.join(timeout=10)
        assert outcome == ["ROLL_WRONG_STATUS"]
        with Session(engine) as check:
            assert check.scalar(select(func.count()).select_from(RollRun).where(RollRun.purpose == "dye")) == 1
    finally:
        wipe_database(engine)


def test_two_real_simultaneous_loads_of_the_same_roll_link_it_once(engine):
    try:
        for _ in range(5):
            _, codes, (dye_a, dye_b) = committed_shop(engine)
            barrier = threading.Barrier(2)
            results: list[str] = []

            def go(run_id, codes=codes, results=results, barrier=barrier):
                with Session(engine) as session:
                    barrier.wait()
                    try:
                        floor_rolls.load_rolls(session, run_id, s.LoadRollsIn(roll_codes=codes))
                        results.append("ok")
                    except AppError as exc:
                        results.append(exc.code)

            threads = [threading.Thread(target=go, args=(r,)) for r in (dye_a, dye_b)]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert sorted(results) == ["ROLL_WRONG_STATUS", "ok"], results
            with Session(engine) as check:
                roll_id = check.scalar(select(Roll.id).where(Roll.code == codes[0]))
                assert check.scalar(select(func.count()).select_from(RollRun).where(
                    RollRun.roll_id == roll_id, RollRun.purpose == "dye")) == 1
            wipe_database(engine)
    finally:
        wipe_database(engine)
