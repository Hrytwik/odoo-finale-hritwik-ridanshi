"""B2 Task 3: receiving a lot (R1) and reading lots. Hand-worked numbers: 800 kg at 250 = 200,000.00."""
import datetime as dt
import re
import threading
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import SupplierBill, YarnLot, YarnMovement
from app.modules.store import schemas as s
from app.modules.store import service
from tests.factories import (
    make_lot, make_order, make_supplier, make_user, make_yarn_type, make_run, make_machine,
)

PHOTO = "uploads/" + "ab12" * 8 + ".jpg"


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


@pytest.fixture
def base(db, login_as):
    user = login_as("store")
    return {"user": user, "yt": make_yarn_type(db), "supplier": make_supplier(db)}


def body(base, **over):
    data = {"yarn_type_id": base["yt"].id, "supplier_id": base["supplier"].id, "qty_kg": 800,
            "cost_per_kg": 250, "challan_no": "CH-5521"}
    return {**data, **over}


def counts(db):
    return tuple(db.scalar(select(func.count()).select_from(t)) for t in (YarnLot, YarnMovement, SupplierBill))


def test_receive_creates_lot_receipt_and_bill_with_the_worked_numbers(client, db, base, events):
    r = client.post("/api/lots", json=body(base, challan_photo_path=PHOTO))
    assert r.status_code == 201, r.text
    out = r.json()
    assert re.fullmatch(r"L-\d{4,}", out["lot_code"])
    assert out["qty_received_kg"] == 800 and out["on_hand_kg"] == 800 and out["cost_per_kg"] == 250
    assert out["challan_photo_url"] == "/api/uploads/" + PHOTO.removeprefix("uploads/")
    assert out["yarn_type"]["id"] == base["yt"].id and out["supplier"]["id"] == base["supplier"].id
    assert out["is_blocked"] is False and out["intended_order_code"] is None
    lot = db.scalar(select(YarnLot).where(YarnLot.lot_code == out["lot_code"]))
    assert lot.received_by == base["user"].id
    [move] = lot.movements
    assert (move.kind, move.qty_kg, move.moved_by) == ("receipt", Decimal("800.000"), base["user"].id)
    assert lot.bill.amount == Decimal("200000.00") and lot.bill.bill_no == "CH-5521"
    assert lot.bill.supplier_id == base["supplier"].id
    assert lot.bill.due_date - lot.bill.bill_date == dt.timedelta(days=30)
    ist = ZoneInfo("Asia/Kolkata")
    assert lot.bill.bill_date in {dt.datetime.now(ist).date(), dt.datetime.now(ist).date() - dt.timedelta(days=1)}


def test_intended_order_code_is_returned(client, db, base):
    order = make_order(db)
    r = client.post("/api/lots", json=body(base, intended_order_code=order.code))
    assert r.status_code == 201 and r.json()["intended_order_code"] == order.code


def test_events_are_published_once_after_success_and_not_after_a_conflict(client, base, events):
    assert client.post("/api/lots", json=body(base)).status_code == 201
    first = list(events)
    assert [k for k, _ in first] == ["lot.changed", "stock.changed"]
    assert client.post("/api/lots", json=body(base)).status_code == 409
    assert events == first


def test_duplicate_challan_is_409_and_leaves_nothing_behind(client, db, base):
    assert client.post("/api/lots", json=body(base)).status_code == 201
    before = counts(db)
    r = client.post("/api/lots", json=body(base))
    assert r.status_code == 409
    assert r.json()["code"] == "DUPLICATE_CHALLAN" and r.json()["field"] == "challan_no"
    assert counts(db) == before


def test_same_challan_for_another_supplier_or_yarn_type_is_fine(client, db, base):
    assert client.post("/api/lots", json=body(base)).status_code == 201
    other_supplier = make_supplier(db)
    other_yarn = make_yarn_type(db)
    assert client.post("/api/lots", json=body(base, supplier_id=other_supplier.id)).status_code == 201
    assert client.post("/api/lots", json=body(base, yarn_type_id=other_yarn.id)).status_code == 201


@pytest.mark.parametrize("over, field", [
    ({"yarn_type_id": 999999}, "yarn_type_id"),
    ({"supplier_id": 999999}, "supplier_id"),
    ({"intended_order_code": "ORD-9999"}, "intended_order_code"),
])
def test_unknown_references_are_404_on_the_right_field(client, db, base, events, over, field):
    before = counts(db)
    r = client.post("/api/lots", json=body(base, **over))
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND" and r.json()["field"] == field
    assert counts(db) == before and events == []


@pytest.mark.parametrize("path", [
    "../../etc/passwd", "http://evil.example/x.jpg", "uploads/../secret.jpg", "/uploads/" + "ab12" * 8 + ".jpg",
    "uploads/" + "AB12" * 8 + ".jpg", "uploads/" + "ab12" * 8 + ".gif", "uploads/" + "ab12" * 7 + ".jpg",
    "uploads/" + "ab12" * 8 + ".jpg/../../x.jpg",
])
def test_bad_photo_paths_are_rejected_and_never_stored(client, db, base, path):
    before = counts(db)
    r = client.post("/api/lots", json=body(base, challan_photo_path=path))
    assert r.status_code == 422 and r.json()["field"] == "challan_photo_path"
    assert counts(db) == before


@pytest.mark.parametrize("name", ["x.jpg", "uploads/" + "ab12" * 8 + ".jpg\n"])
def test_photo_regex_uses_a_full_match(db, base, name):
    with pytest.raises(AppError) as err:
        service.receive_lot(db, base["user"], s.LotReceiveIn.model_construct(**body(base, challan_photo_path=name)))
    assert err.value.status == 422 and err.value.field == "challan_photo_path"


@pytest.mark.parametrize("qty", ["0.0004", "1e9", '"abc"', "NaN", "Infinity", "-5", "0", "true", "null"])
def test_bad_quantities_are_a_clean_422_on_qty_kg(client, db, base, qty):
    before = counts(db)
    raw = ('{"yarn_type_id": %d, "supplier_id": %d, "qty_kg": %s, "cost_per_kg": 250, "challan_no": "CH-1"}'
           % (base["yt"].id, base["supplier"].id, qty))
    r = client.post("/api/lots", content=raw, headers={"content-type": "application/json"})
    assert r.status_code == 422, r.text
    assert "qty_kg" in (r.json().get("fields") or {r.json()["field"]: ""})
    assert counts(db) == before


@pytest.mark.parametrize("cost", ["0.004", "0", "-1", "1e12", '"abc"'])
def test_bad_costs_are_a_clean_422_on_cost_per_kg(client, db, base, cost):
    before = counts(db)
    raw = ('{"yarn_type_id": %d, "supplier_id": %d, "qty_kg": 5, "cost_per_kg": %s, "challan_no": "CH-1"}'
           % (base["yt"].id, base["supplier"].id, cost))
    r = client.post("/api/lots", content=raw, headers={"content-type": "application/json"})
    assert r.status_code == 422 and "cost_per_kg" in (r.json().get("fields") or {r.json()["field"]: ""})
    assert counts(db) == before


def test_four_decimal_inputs_round_half_up_and_the_bill_uses_the_rounded_numbers(client, db, base):
    r = client.post("/api/lots", json=body(base, qty_kg=1.0005, cost_per_kg=2.675))
    assert r.status_code == 201, r.text
    lot = db.scalar(select(YarnLot).where(YarnLot.lot_code == r.json()["lot_code"]))
    assert lot.movements[0].qty_kg == Decimal("1.001") and lot.cost_per_kg == Decimal("2.68")
    assert lot.bill.amount == Decimal("2.68")  # 1.001 x 2.68 = 2.68268 -> 2.68
    assert r.json()["qty_received_kg"] == 1.001 and r.json()["cost_per_kg"] == 2.68


def test_several_bad_fields_are_all_reported(client, base):
    r = client.post("/api/lots", json=body(base, qty_kg=0, challan_no="  "))
    assert r.status_code == 422 and set(r.json()["fields"]) == {"qty_kg", "challan_no"}


def test_the_smallest_accepted_quantity_is_one_gram(client, base):
    assert client.post("/api/lots", json=body(base, qty_kg=0.001)).status_code == 201


def test_list_and_filters(client, db, login_as):
    login_as("accountant")
    yt_a, yt_b = make_yarn_type(db), make_yarn_type(db)
    a = make_lot(db, yarn_type=yt_a)
    b = make_lot(db, yarn_type=yt_b)
    b.is_blocked, b.blocked_reason, b.blocked_at = True, "damp", dt.datetime(2026, 10, 2, tzinfo=dt.UTC)
    db.flush()
    codes = lambda r: {x["lot_code"] for x in r.json()}  # noqa: E731
    assert codes(client.get("/api/lots")) >= {a.lot_code, b.lot_code}
    assert codes(client.get(f"/api/lots?yarn_type_id={yt_a.id}")) == {a.lot_code}
    assert codes(client.get("/api/lots?blocked=true")) == {b.lot_code}
    assert a.lot_code in codes(client.get("/api/lots?blocked=false"))
    assert b.lot_code not in codes(client.get("/api/lots?blocked=false"))
    blocked = client.get("/api/lots?blocked=true").json()[0]
    assert blocked["is_blocked"] is True and blocked["blocked_reason"] == "damp"


def test_list_is_newest_first(client, db, login_as):
    login_as("owner")
    first, second = make_lot(db), make_lot(db)
    codes = [x["lot_code"] for x in client.get("/api/lots").json()]
    assert codes.index(second.lot_code) < codes.index(first.lot_code)


def test_detail_has_movements_oldest_first_with_run_details(client, db, login_as):
    login_as("supervisor")
    lot = make_lot(db, qty_kg=800)
    order = make_order(db)
    run = make_run(db, order, make_machine(db, stage="spinning"))
    user = make_user(db, role="supervisor")
    db.add_all([
        YarnMovement(yarn_lot_id=lot.id, kind="issue", qty_kg=Decimal("-587.5"), production_run_id=run.id,
                     moved_by=user.id),
        YarnMovement(yarn_lot_id=lot.id, kind="return", qty_kg=Decimal("20"), production_run_id=run.id,
                     moved_by=user.id),
    ])
    db.flush()
    r = client.get(f"/api/lots/{lot.lot_code}")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["qty_received_kg"] == 800 and out["on_hand_kg"] == 232.5
    kinds = [m["kind"] for m in out["movements"]]
    assert kinds == ["receipt", "issue", "return"]
    issue = out["movements"][1]
    assert issue["qty_kg"] == -587.5 and issue["run_id"] == run.id and issue["order_code"] == order.code
    assert issue["machine_code"] == run.machine.code and issue["by"] == user.username and issue["lot_code"] == lot.lot_code
    assert out["movements"][0]["run_id"] is None and out["movements"][0]["order_code"] is None


def test_unknown_lot_is_404(client, login_as):
    login_as("owner")
    r = client.get("/api/lots/L-9999999")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


@pytest.mark.parametrize("role", ["buyer", "qc", "dispatch"])
def test_other_roles_cannot_read_lots(client, login_as, role):
    login_as(role)
    assert client.get("/api/lots").status_code == 403


@pytest.mark.parametrize("role", ["supervisor", "accountant", "qc", "dispatch", "buyer"])
def test_only_store_and_owner_receive(client, db, login_as, role):
    login_as(role)
    yt, sup = make_yarn_type(db), make_supplier(db)
    r = client.post("/api/lots", json={"yarn_type_id": yt.id, "supplier_id": sup.id, "qty_kg": 5,
                                       "cost_per_kg": 10, "challan_no": "CH-9"})
    assert r.status_code == 403


def test_owner_can_receive(client, db, login_as):
    login_as("owner")
    yt, sup = make_yarn_type(db), make_supplier(db)
    r = client.post("/api/lots", json={"yarn_type_id": yt.id, "supplier_id": sup.id, "qty_kg": 5,
                                       "cost_per_kg": 10, "challan_no": "CH-9"})
    assert r.status_code == 201


def test_two_simultaneous_receives_of_the_same_challan_give_one_lot(engine):
    """Review Focus 2: separate sessions on committed data; one 201-equivalent and one DUPLICATE_CHALLAN."""
    with Session(engine) as setup:
        user = make_user(setup, role="store")
        yt, sup = make_yarn_type(setup), make_supplier(setup)
        setup.commit()
        user_id, yt_id, sup_id = user.id, yt.id, sup.id
    barrier = threading.Barrier(2)
    results: list[object] = []

    def receive():
        with Session(engine) as session:
            actor = session.get(type(user), user_id)
            payload = s.LotReceiveIn(yarn_type_id=yt_id, supplier_id=sup_id, qty_kg=100, cost_per_kg=10,
                                     challan_no="CH-RACE")
            barrier.wait()
            try:
                results.append(service.receive_lot(session, actor, payload).lot_code)
            except AppError as exc:
                results.append(exc.code)

    try:
        threads = [threading.Thread(target=receive) for _ in range(2)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert sorted(results, key=lambda r: r != "DUPLICATE_CHALLAN")[0] == "DUPLICATE_CHALLAN", results
        assert sum(r == "DUPLICATE_CHALLAN" for r in results) == 1 and len(results) == 2
        with Session(engine) as check:
            assert check.scalar(select(func.count()).select_from(YarnLot).where(YarnLot.supplier_id == sup_id)) == 1
            assert check.scalar(select(func.count()).select_from(SupplierBill).where(
                SupplierBill.supplier_id == sup_id)) == 1
            lot_id = check.scalar(select(YarnLot.id).where(YarnLot.supplier_id == sup_id))
            assert check.scalar(select(func.count()).select_from(YarnMovement).where(
                YarnMovement.yarn_lot_id == lot_id)) == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text(
                "TRUNCATE supplier_bills, yarn_movements, yarn_lots, suppliers, yarn_types, users RESTART IDENTITY CASCADE"))
