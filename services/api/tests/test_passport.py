"""B4 Task 5: the Roll Passport. The whole life of one roll; a buyer sees only their own rolls, and a roll that is not theirs
looks exactly like a roll that does not exist (R15)."""
import datetime as dt
from decimal import Decimal

import pytest
from app.db.models import Invoice, RollRun, Worker
from tests.factories import (
    dye, make_buyer, make_dispatch, make_fabric_type, make_inspection, make_lot, make_machine, make_order, make_roll,
    make_run, make_supplier, make_user, make_worker, make_yarn_type, put_on_dispatch,
)
from tests.test_stock_views import give_back, issue

T0 = dt.datetime(2026, 10, 1, 8, tzinfo=dt.UTC)


def passport(client, roll):
    r = client.get(f"/api/rolls/{roll.code}/passport")
    return r


class Life:
    """spinning (yarn issued) -> weaving -> dyeing -> one roll, ready to be inspected."""

    def __init__(self, db, buyer=None):
        self.db = db
        self.cotton = make_yarn_type(db, name="30s cotton")
        self.supplier = make_supplier(db, name="Vardhman Yarns")
        self.order = make_order(db, buyer=buyer, fabric_type=make_fabric_type(db, yarn_type=self.cotton), qty_metres=1000)
        self.lot = make_lot(db, yarn_type=self.cotton, supplier=self.supplier, qty_kg=800)
        self.spin_machine = make_machine(db, stage="spinning", name="Ring frame 1")
        self.spin = make_run(db, self.order, self.spin_machine, started_at=T0, ended_at=T0 + dt.timedelta(hours=5))
        issue(db, self.lot, self.spin, 587.5)
        self.loom = make_machine(db, stage="weaving", name="Loom 4")
        self.weave = make_run(db, self.order, self.loom, input_run_id=self.spin.id, started_at=T0 + dt.timedelta(hours=6))
        self.roll = make_roll(db, self.order, self.weave, 110)
        self.dyer = make_machine(db, stage="dyeing", name="Jet dyer 1")
        self.dye = make_run(db, self.order, self.dyer, started_at=T0 + dt.timedelta(hours=8),
                            ended_at=T0 + dt.timedelta(hours=12))
        dye(db, self.roll, self.dye)


@pytest.fixture
def owner(login_as):
    return login_as("owner")


def test_a_full_life_in_order(client, db, owner):
    life = Life(db)
    make_inspection(db, life.roll, "rework", inspected_at=T0 + dt.timedelta(days=1))
    rework = make_run(db, life.order, make_machine(db, stage="dyeing"), stage="rework", started_at=T0 + dt.timedelta(days=2),
                      ended_at=T0 + dt.timedelta(days=2, hours=3))
    db.add(RollRun(roll_id=life.roll.id, run_id=rework.id, purpose="rework"))
    db.flush()
    make_inspection(db, life.roll, "pass", inspected_at=T0 + dt.timedelta(days=3))
    r = passport(client, life.roll)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["roll"]["code"] == life.roll.code and p["roll"]["status"] == "in_store" and p["roll"]["metres"] == 110.0
    assert (p["order_code"], p["buyer_name"]) == (life.order.code, life.order.buyer.name)
    assert p["deadline"] == str(life.order.deadline)
    assert [(x["stage"], x["id"]) for x in p["runs"]] == [("spinning", life.spin.id), ("weaving", life.weave.id),
                                                          ("dyeing", life.dye.id), ("rework", rework.id)]
    spin = p["runs"][0]
    assert spin["machine_code"] == life.spin_machine.code and spin["machine_name"] == "Ring frame 1"
    assert spin["operator"] == life.spin.operator.name and spin["ended_at"] is not None
    assert [(l["lot_code"], l["yarn_type"], l["supplier"], l["is_blocked"]) for l in p["yarn_lots"]] == [
        (life.lot.lot_code, "30s cotton", "Vardhman Yarns", False)]
    assert [i["verdict"] for i in p["inspections"]] == ["rework", "pass"]
    assert p["cost"]["roll_code"] == life.roll.code and p["dispatch"] is None       # an owner sees the real cost (R18)


def test_the_yarn_trace_counts_net_issues_only(client, db, owner):
    life = Life(db)
    returned = make_lot(db, yarn_type=life.cotton, supplier=life.supplier, qty_kg=500)
    issue(db, returned, life.spin, 300)
    give_back(db, returned, life.spin, 300)                      # fully returned: not in the roll
    partly = make_lot(db, yarn_type=life.cotton, supplier=life.supplier, qty_kg=500)
    issue(db, partly, life.spin, 100)
    give_back(db, partly, life.spin, 20)                          # 80 kg net: in the roll
    elsewhere = make_lot(db, yarn_type=life.cotton, supplier=life.supplier, qty_kg=500)
    other_spin = make_run(db, life.order, make_machine(db, stage="spinning"))
    issue(db, elsewhere, other_spin, 100)                         # issued to a different spinning run: not in the roll
    codes = {l["lot_code"] for l in passport(client, life.roll).json()["yarn_lots"]}
    assert codes == {life.lot.lot_code, partly.lot_code} and returned.lot_code not in codes


def test_a_blocked_lot_is_flagged(client, db, owner):
    life = Life(db)
    life.lot.is_blocked, life.lot.blocked_reason, life.lot.blocked_at = True, "damp", T0
    db.flush()
    assert passport(client, life.roll).json()["yarn_lots"][0]["is_blocked"] is True


def test_hand_overs_show_each_run_once_in_order(client, db, login_as):
    login_as("supervisor")
    life = Life(db)
    life.dye.ended_at = None                                       # make the dyeing run open so it can be handed over
    db.flush()
    sup_worker = make_worker(db)
    r = client.post(f"/api/runs/{life.dye.id}/handover", json={"operator_worker_id": sup_worker.id})
    assert r.status_code == 201
    new_dye = r.json()["id"]
    p = passport(client, life.roll).json()
    ids = [x["id"] for x in p["runs"]]
    assert ids == [life.spin.id, life.weave.id, life.dye.id, new_dye] and len(ids) == len(set(ids))
    assert p["roll"]["status"] == "dyeing"


def test_a_roll_on_a_dispatch_shows_it(client, db, owner):
    life = Life(db)
    make_inspection(db, life.roll, "pass", inspected_at=T0 + dt.timedelta(days=1))
    dispatch = make_dispatch(db, life.order.buyer, vehicle_no="KA01AB1234")
    put_on_dispatch(db, life.roll, dispatch)
    p = passport(client, life.roll).json()
    assert p["dispatch"] == {"code": dispatch.code, "dispatched_at": None, "vehicle_no": "KA01AB1234", "invoice_no": None}
    dispatch.state, dispatch.dispatched_at = "dispatched", T0 + dt.timedelta(days=2)
    db.add(Invoice(invoice_no="INV-0001", dispatch_id=dispatch.id, buyer_id=life.order.buyer_id,
                   issued_at=T0 + dt.timedelta(days=2), total_amount=Decimal("13200.00")))
    db.flush()
    p = passport(client, life.roll).json()
    assert p["roll"]["status"] == "dispatched" and p["dispatch"]["invoice_no"] == "INV-0001"
    assert p["dispatch"]["dispatched_at"] is not None


def test_staff_see_inspector_names_photos_and_ai_output(client, db, owner):
    life = Life(db)
    inspection = make_inspection(db, life.roll, "rework", inspected_at=T0 + dt.timedelta(days=1),
                                 photo_path="uploads/" + "ab12" * 8 + ".jpg",
                                 ai_suggestion={"model_version": "yolo-1", "verdict": "rework", "boxes": []})
    p = passport(client, life.roll).json()
    [i] = p["inspections"]
    assert i["inspector"]["name"] == db.get(Worker, inspection.inspector_worker_id).name
    assert i["photo_url"] == "/api/uploads/" + "ab12" * 8 + ".jpg" and i["ai_suggestion"]["model_version"] == "yolo-1"


# ---- buyers (R15) -------------------------------------------------------------------------------------

def test_a_buyer_sees_only_status_order_quality_and_dispatch(client, db, login_as):
    buyer_user = login_as("buyer")
    life = Life(db, buyer=buyer_user.buyer)
    make_inspection(db, life.roll, "pass", inspected_at=T0 + dt.timedelta(days=1),
                    photo_path="uploads/" + "ab12" * 8 + ".jpg",
                    ai_suggestion={"model_version": "yolo-1", "verdict": "pass", "boxes": []})
    r = passport(client, life.roll)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["cost"] is None and p["yarn_lots"] == [] and p["runs"] == []
    [i] = p["inspections"]
    assert i["inspector"] == {"id": 0, "name": "Quality team"} and i["photo_url"] is None and i["ai_suggestion"] is None
    assert i["verdict"] == "pass" and p["roll"]["status"] == "in_store" and p["order_code"] == life.order.code


def test_another_buyers_roll_and_a_missing_roll_look_identical(client, db, login_as):
    login_as("buyer")
    foreign = Life(db, buyer=make_buyer(db))                       # an order of a different buyer
    mine_but_missing = client.get("/api/rolls/R-9999999/passport")
    theirs = passport(client, foreign.roll)
    assert theirs.status_code == mine_but_missing.status_code == 404
    assert theirs.content == mine_but_missing.content              # byte-identical: nothing leaks through the message
    assert theirs.json()["code"] == "NOT_FOUND" and theirs.json()["field"] == "roll_code"


@pytest.mark.parametrize("role", ["owner", "accountant", "store", "supervisor", "qc", "dispatch"])
def test_every_staff_role_can_read_a_passport(client, db, login_as, role):
    login_as(role)
    life = Life(db)
    assert passport(client, life.roll).status_code == 200


def test_staff_get_404_for_an_unknown_roll_and_anonymous_gets_401(client, db, login_as):
    login_as("owner")
    r = client.get("/api/rolls/R-9999999/passport")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"
    client.cookies.clear()
    assert client.get("/api/rolls/R-9999999/passport").status_code == 401


def test_buyer_view_removes_cost_even_when_a_passport_has_one():
    """The endpoint tests (tests/test_costing_api.py) show a buyer's raw response carries no cost. This pins the
    projection itself: the example passport carries a cost, lots, runs, inspector names, photo and AI output."""
    from app.modules.passport.examples import PASSPORT
    from app.modules.passport.service import buyer_view

    assert PASSPORT.cost is not None and PASSPORT.yarn_lots and PASSPORT.runs
    seen = buyer_view(PASSPORT)
    assert seen.cost is None and seen.yarn_lots == [] and seen.runs == []
    assert all(i.inspector.name == "Quality team" and i.photo_url is None and i.ai_suggestion is None
               for i in seen.inspections)
    assert seen.roll == PASSPORT.roll and seen.order_code == PASSPORT.order_code and seen.dispatch == PASSPORT.dispatch
