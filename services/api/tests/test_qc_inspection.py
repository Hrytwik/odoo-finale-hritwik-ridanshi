"""B4 Task 2: record an inspection (R9). The inspector is the logged-in user's worker; the roll must be awaiting_qc;
a verdict other than pass needs defects; overrode_ai is worked out on the server."""
import datetime as dt
import threading
import time

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import QcInspection, Roll, RollRun, User
from app.modules.qc import schemas as s
from app.modules.qc import service
from tests.factories import (
    dye, make_dispatch, make_inspection, make_machine, make_order, make_roll, make_run, make_user, make_worker,
    put_on_dispatch,
)
from tests.helpers import wipe_database

PHOTO = "uploads/" + "ab12" * 8 + ".jpg"


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


class Floor:
    """An order of 1,000 m and one 100 m roll."""

    def __init__(self, db):
        self.db = db
        self.order = make_order(db, qty_metres=1000)
        self.weave = make_run(db, self.order, make_machine(db, stage="weaving"))
        self.roll = make_roll(db, self.order, self.weave, 100)

    def finish_dyeing(self):
        run = make_run(self.db, self.order, make_machine(self.db, stage="dyeing"))
        dye(self.db, self.roll, run)
        run.ended_at = run.started_at
        self.db.flush()
        return run


@pytest.fixture
def awaiting(db):
    f = Floor(db)
    f.finish_dyeing()
    return f


@pytest.fixture
def qc(login_as):
    return login_as("qc")


def inspect(client, roll, verdict="pass", defects=None, **over):
    body = {"roll_code": roll.code, "verdict": verdict, "defects": defects if defects is not None else [], **over}
    return client.post("/api/qc/inspections", json=body)


def roll_status(client, roll):
    return next(r["status"] for r in client.get(f"/api/rolls?order_code={roll.order.code}").json() if r["code"] == roll.code)


def inspection_count(db) -> int:
    return db.scalar(select(func.count()).select_from(QcInspection))


HOLE = {"defect_type": "hole", "count": 2}


# ---- verdicts -----------------------------------------------------------------------------------

def test_pass_makes_the_roll_in_store_and_counts_its_metres(client, db, qc, awaiting, events):
    r = inspect(client, awaiting.roll, "pass", notes="  clean  ")
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["roll_code"] == awaiting.roll.code and out["verdict"] == "pass" and out["overrode_ai"] is False
    assert out["defects"] == [] and out["notes"] == "clean" and out["photo_url"] is None and out["ai_suggestion"] is None
    assert out["inspector"]["id"] == qc.worker_id and out["inspector"]["name"] == qc.worker.name and out["inspected_at"]
    assert roll_status(client, awaiting.roll) == "in_store"
    assert events == [("roll.changed", awaiting.roll.id), ("order.changed", awaiting.order.id)]


def test_rework_and_reject_flip_the_status_and_the_order_numbers(client, db, login_as):
    login_as("qc")
    for verdict, status, passed, rejected in (("rework", "awaiting_rework", 0.0, 0.0), ("reject", "rejected", 0.0, 100.0)):
        f = Floor(db)
        f.finish_dyeing()
        r = inspect(client, f.roll, verdict, [HOLE, {"defect_type": "stain", "count": 1, "ai_detected": True}])
        assert r.status_code == 201, r.text
        assert [(d["defect_type"], d["count"], d["ai_detected"]) for d in r.json()["defects"]] == [
            ("hole", 2, False), ("stain", 1, True)]
        assert roll_status(client, f.roll) == status
    login_as("owner")
    assert client.get(f"/api/orders/{f.order.code}").json()["progress"]["rejected_m"] == 100.0


def test_a_pass_adds_to_the_orders_passed_metres(client, db, login_as):
    login_as("qc")
    f = Floor(db)
    f.finish_dyeing()
    assert inspect(client, f.roll, "pass").status_code == 201
    login_as("owner")
    p = client.get(f"/api/orders/{f.order.code}").json()["progress"]
    assert (p["passed_m"], p["rejected_m"]) == (100.0, 0.0)


def test_defects_are_required_unless_the_verdict_is_pass(client, db, qc, awaiting, events):
    for verdict in ("rework", "reject"):
        r = inspect(client, awaiting.roll, verdict)
        assert r.status_code == 422 and r.json()["code"] == "DEFECTS_REQUIRED" and r.json()["field"] == "defects"
    assert inspection_count(db) == 0 and events == [] and roll_status(client, awaiting.roll) == "awaiting_qc"


def test_a_pass_with_defects_is_allowed_and_keeps_them(client, db, qc, awaiting):
    r = inspect(client, awaiting.roll, "pass", [{"defect_type": "other", "count": 1}])
    assert r.status_code == 201 and len(r.json()["defects"]) == 1 and roll_status(client, awaiting.roll) == "in_store"


def test_the_same_defect_type_twice_is_refused(client, db, qc, awaiting, events):
    r = inspect(client, awaiting.roll, "rework", [HOLE, {"defect_type": "hole", "count": 1}])
    assert r.status_code == 422 and r.json()["field"] == "defects"
    assert inspection_count(db) == 0 and events == []


# ---- the roll must be awaiting_qc ---------------------------------------------------------------

def test_every_other_status_is_refused_and_nothing_is_stored(client, db, qc, events):
    cases = {}
    f = Floor(db)
    cases["woven"] = f.roll
    f = Floor(db)
    run = make_run(db, f.order, make_machine(db, stage="dyeing"))
    dye(db, f.roll, run)
    cases["dyeing"] = f.roll
    for verdict, name in (("pass", "in_store"), ("reject", "rejected"), ("rework", "awaiting_rework")):
        f = Floor(db)
        f.finish_dyeing()
        make_inspection(db, f.roll, verdict)
        cases[name] = f.roll
    f = Floor(db)
    f.finish_dyeing()
    make_inspection(db, f.roll, "pass")
    put_on_dispatch(db, f.roll, make_dispatch(db, f.order.buyer, state="dispatched", dispatched_at=dt.datetime(2026, 10, 9, tzinfo=dt.UTC)))
    cases["dispatched"] = f.roll
    before = inspection_count(db)
    for name, roll in cases.items():
        r = inspect(client, roll, "pass")
        assert r.status_code == 409 and r.json()["code"] == "ROLL_WRONG_STATUS" and r.json()["field"] == "roll_code", name
        assert name in r.json()["message"], (name, r.json()["message"])
    assert inspection_count(db) == before and events == []


def test_an_unknown_roll_is_404(client, db, qc):
    r = client.post("/api/qc/inspections", json={"roll_code": "R-9999999", "verdict": "pass", "defects": []})
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND" and r.json()["field"] == "roll_code"


# ---- photos -------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "../../etc/passwd", "http://evil.example/x.jpg", "uploads/../secret.jpg", "/uploads/" + "ab12" * 8 + ".jpg",
    "uploads/" + "AB12" * 8 + ".jpg", "uploads/" + "ab12" * 8 + ".gif", "uploads/" + "ab12" * 7 + ".jpg",
    "uploads/" + "ab12" * 8 + ".jpg/../../x.jpg",
])
def test_bad_photo_paths_are_refused(client, db, qc, awaiting, events, path):
    r = inspect(client, awaiting.roll, "pass", photo_path=path)
    assert r.status_code == 422 and r.json()["field"] == "photo_path"
    assert inspection_count(db) == 0 and events == []


def test_a_good_photo_path_becomes_a_url(client, db, qc, awaiting):
    r = inspect(client, awaiting.roll, "pass", photo_path=PHOTO)
    assert r.status_code == 201 and r.json()["photo_url"] == "/api/" + PHOTO


# ---- overrode_ai --------------------------------------------------------------------------------

SUGGESTION = {"model_version": "yolo-1", "verdict": "rework",
              "boxes": [{"x": 0.4, "y": 0.3, "w": 0.1, "h": 0.1, "defect_type": "hole", "confidence": 0.9}]}


@pytest.mark.parametrize("verdict, expected", [("pass", True), ("rework", False), ("reject", True)])
def test_overrode_ai_compares_the_verdicts(client, db, qc, awaiting, verdict, expected):
    defects = [HOLE] if verdict != "pass" else []
    r = inspect(client, awaiting.roll, verdict, defects, ai_suggestion=SUGGESTION)
    assert r.status_code == 201 and r.json()["overrode_ai"] is expected
    assert r.json()["ai_suggestion"] == SUGGESTION                        # stored exactly as sent


def test_no_suggestion_is_never_an_override(client, db, qc, awaiting):
    assert inspect(client, awaiting.roll, "pass").json()["overrode_ai"] is False


# ---- who is the inspector -------------------------------------------------------------------------

def test_the_owner_has_no_worker_and_cannot_inspect(client, db, login_as, awaiting, events):
    login_as("owner")
    r = inspect(client, awaiting.roll, "pass")
    assert r.status_code == 409 and r.json()["code"] == "INSPECTOR_REQUIRED"
    assert inspection_count(db) == 0 and events == []


def test_an_owner_linked_to_an_active_worker_can_inspect(client, db, login_as, awaiting):
    owner = login_as("owner", worker_id=make_worker(db, role="inspector").id)
    assert inspect(client, awaiting.roll, "pass").status_code == 201 and owner.worker_id


def test_a_qc_login_with_an_inactive_worker_is_refused(client, db, login_as, awaiting):
    qc = login_as("qc")
    qc.worker.active = False
    db.flush()
    r = inspect(client, awaiting.roll, "pass")
    assert r.status_code == 409 and r.json()["code"] == "INSPECTOR_REQUIRED"


@pytest.mark.parametrize("role", ["supervisor", "store", "dispatch", "accountant", "buyer"])
def test_other_roles_cannot_inspect(client, db, login_as, awaiting, role):
    login_as(role)
    assert inspect(client, awaiting.roll, "pass").status_code == 403


# ---- the clock, and two inspectors at the same moment -----------------------------------------------

def committed_roll(engine, qc_users=2):
    with Session(engine) as setup:
        f = Floor(setup)
        f.finish_dyeing()
        users = [make_user(setup, role="qc") for _ in range(qc_users)]
        setup.commit()
        return f.roll.id, f.roll.code, [u.id for u in users]


def test_inspected_at_is_the_real_time_of_the_write(engine):
    roll_id, code, user_ids = committed_roll(engine, 1)
    try:
        with Session(engine) as session:
            began = session.scalar(text("SELECT now()"))
            time.sleep(0.2)
            insp = service.record_inspection(session, session.get(User, user_ids[0]),
                                             s.InspectionIn(roll_code=code, verdict="pass", defects=[]))
            assert (insp.inspected_at - began).total_seconds() >= 0.15
    finally:
        wipe_database(engine)


def fight(engine, code, user_ids):
    barrier = threading.Barrier(len(user_ids))
    results: list[str] = []

    def go(user_id):
        with Session(engine) as session:
            body = s.InspectionIn(roll_code=code, verdict="pass", defects=[])
            user = session.get(User, user_id)
            barrier.wait()
            try:
                service.record_inspection(session, user, body)
                results.append("ok")
            except AppError as exc:
                results.append(exc.code)

    threads = [threading.Thread(target=go, args=(u,)) for u in user_ids]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return sorted(results)


def test_two_inspectors_on_one_roll_at_once_give_one_verdict(engine):
    try:
        for _ in range(5):
            roll_id, code, user_ids = committed_roll(engine)
            assert fight(engine, code, user_ids) == ["ROLL_WRONG_STATUS", "ok"]
            with Session(engine) as check:
                assert check.scalar(select(func.count()).select_from(QcInspection).where(QcInspection.roll_id == roll_id)) == 1
            wipe_database(engine)
    finally:
        wipe_database(engine)


def test_an_inspection_waits_for_whoever_holds_the_roll_lock(engine):
    roll_id, code, user_ids = committed_roll(engine, 2)
    outcome: list[str] = []

    def second():
        with Session(engine) as session:
            try:
                service.record_inspection(session, session.get(User, user_ids[1]),
                                          s.InspectionIn(roll_code=code, verdict="pass", defects=[]))
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            holder.scalar(select(Roll).where(Roll.id == roll_id).with_for_update())     # inspector A has the roll
            thread = threading.Thread(target=second)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "inspector B must be waiting on the roll lock"
            worker_id = holder.get(User, user_ids[0]).worker_id
            holder.add(QcInspection(roll_id=roll_id, inspector_worker_id=worker_id, verdict="pass"))
            holder.commit()
            thread.join(timeout=10)
        assert outcome == ["ROLL_WRONG_STATUS"]
    finally:
        wipe_database(engine)
