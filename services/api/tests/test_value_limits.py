"""B5 Task 1: a text value longer than its column, or a number larger than its column, is a clean 422, never a server error.
All money columns are numeric(12,2) (largest 9,999,999,999.99); challan_no is 60 characters, order colour 60.
(A real database failure rolls back the whole test transaction, so each such case is the last step of its test.)"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from app.core.errors import AppError, install_error_handlers
from app.db.models import SupplierBill, YarnLot, YarnMovement
from app.modules.store import schemas as ss
from app.modules.store import service as store
from tests.factories import make_buyer, make_fabric_type, make_supplier, make_user, make_yarn_type
from tests.helpers import wipe_database


def lot_body(yt, sup, **over):
    return {"yarn_type_id": yt.id, "supplier_id": sup.id, "qty_kg": 5, "cost_per_kg": 10, "challan_no": "CH-1", **over}


def test_a_challan_number_at_the_limit_is_accepted(client, db, login_as):
    login_as("store")
    yt, sup = make_yarn_type(db), make_supplier(db)
    assert client.post("/api/lots", json=lot_body(yt, sup, challan_no="C" * 60)).status_code == 201


@pytest.mark.parametrize("length", [61, 200])
def test_a_challan_number_over_the_limit_is_a_clean_422(client, db, login_as, length):
    login_as("store")
    yt, sup = make_yarn_type(db), make_supplier(db)
    r = client.post("/api/lots", json=lot_body(yt, sup, challan_no="C" * length))
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "VALUE_TOO_LONG" and "60" in r.json()["message"]


def test_an_order_colour_over_the_limit_is_a_clean_422(client, db, login_as):
    login_as("owner")
    body = {"buyer_id": make_buyer(db).id, "fabric_type_id": make_fabric_type(db).id, "colour": "n" * 61,
            "qty_metres": 100, "price_per_metre": 10, "deadline": "2099-01-01"}
    r = client.post("/api/orders", json=body)
    assert r.status_code == 422 and r.json()["code"] == "VALUE_TOO_LONG" and "60" in r.json()["message"]


def test_a_bill_too_big_for_its_column_is_a_clean_422(client, db, login_as):
    """1,000,000 kg at 100,000,000 a kg is 1e14, far beyond numeric(12,2)."""
    login_as("store")
    yt, sup = make_yarn_type(db), make_supplier(db)
    r = client.post("/api/lots", json=lot_body(yt, sup, qty_kg=1_000_000, cost_per_kg=100_000_000))
    assert r.status_code == 422 and r.json()["code"] == "NUMBER_TOO_LARGE"


def test_nothing_is_left_behind_and_no_event_is_published(engine, monkeypatch):
    """Real sessions on committed data: after the refusal no lot, movement or bill exists."""
    from app.core.events import broadcaster

    published = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: published.append(kind))
    with Session(engine) as setup:
        yt, sup, user = make_yarn_type(setup), make_supplier(setup), make_user(setup, role="store")
        setup.commit()
        ids = (yt.id, sup.id, user.id)
    try:
        with Session(engine) as session:
            body = ss.LotReceiveIn(yarn_type_id=ids[0], supplier_id=ids[1], qty_kg=1_000_000, cost_per_kg=100_000_000,
                                   challan_no="CH-BIG")
            with pytest.raises(AppError) as err:
                store.receive_lot(session, session.get(type(user), ids[2]), body)
            assert err.value.code == "NUMBER_TOO_LARGE" and err.value.status == 422
        with Session(engine) as check:
            for model in (YarnLot, YarnMovement, SupplierBill):
                assert check.scalar(select(func.count()).select_from(model)) == 0, model.__name__
        assert published == []
    finally:
        wipe_database(engine)


def test_an_ordinary_value_still_works_after_the_net_is_in_place(client, db, login_as):
    login_as("store")
    yt, sup = make_yarn_type(db), make_supplier(db)
    r = client.post("/api/lots", json=lot_body(yt, sup, qty_kg=1000, cost_per_kg=250))
    assert r.status_code == 201 and r.json()["qty_received_kg"] == 1000.0


class _Orig(Exception):
    def __init__(self, sqlstate: str, message: str) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate


@pytest.mark.parametrize("sqlstate, message, code, fragment", [
    ("22001", "value too long for type character varying(30)", "VALUE_TOO_LONG", "30"),
    ("22003", "numeric field overflow", "NUMBER_TOO_LARGE", "too large"),
    ("22P02", "invalid input syntax", "INVALID_VALUE", "not allowed"),
])
def test_a_data_error_raised_anywhere_is_still_mapped(sqlstate, message, code, fragment):
    """The shared handler also covers a database data error raised outside commit() and flush() (for example when a
    query triggers an automatic flush)."""
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise DataError("INSERT ...", {}, _Orig(sqlstate, message))

    r = TestClient(app).get("/boom")
    assert r.status_code == 422 and r.json()["code"] == code and fragment in r.json()["message"]
