"""The quality photo log: newest first, filtered by order, batch (yarn lot), result and date, with the inspector's remark."""
import datetime as dt

import pytest

from app.db.models import YarnMovement
from tests.factories import make_inspection, make_lot, make_machine, make_order, make_roll, make_run, make_user


def checked_roll(db, order, lot=None, verdict="pass", **inspection):
    """A roll woven for `order` from `lot` (when given), with one inspection."""
    run = make_run(db, order, make_machine(db, "weaving"))
    if lot is not None:
        db.add(YarnMovement(yarn_lot_id=lot.id, kind="issue", qty_kg=-50, production_run_id=run.input_run_id,
                            moved_by=make_user(db, role="store").id))
        db.flush()
    roll = make_roll(db, order, run, 120)
    return roll, make_inspection(db, roll, verdict, **inspection)


@pytest.fixture
def mill(db):
    order_a, order_b = make_order(db), make_order(db)
    lot_1, lot_2 = make_lot(db), make_lot(db)
    when = lambda day: dt.datetime(2026, 10, day, 9, 0, tzinfo=dt.UTC)  # noqa: E731
    r1, i1 = checked_roll(db, order_a, lot_1, "pass", photo_path="uploads/a.jpg", notes="Clean", inspected_at=when(1))
    r2, i2 = checked_roll(db, order_a, lot_1, "rework", photo_path="uploads/b.jpg", notes="Slub near the edge",
                          inspected_at=when(3), overrode_ai=True,
                          ai_suggestion={"model_version": "m1", "verdict": "pass", "boxes": []})
    r3, i3 = checked_roll(db, order_b, lot_2, "reject", photo_path="uploads/c.jpg", inspected_at=when(5))
    r4, i4 = checked_roll(db, order_b, lot_2, "pass", inspected_at=when(6))  # no photo
    return dict(order_a=order_a, order_b=order_b, lot_1=lot_1, lot_2=lot_2, rolls=[r1, r2, r3, r4])


def codes(body):
    return [i["roll_code"] for i in body["items"]]


def test_the_log_lists_checks_with_photos_newest_first(client, login_as, mill):
    login_as("owner")
    body = client.get("/api/qc/log").json()
    r1, r2, r3, _ = mill["rolls"]
    assert codes(body) == [r3.code, r2.code, r1.code]                       # the roll with no photo is left out
    assert body["counts"] == {"total": 3, "passed": 1, "rework": 1, "rejected": 1, "overrode_ai": 1}
    top = body["items"][0]
    assert top["order_code"] == mill["order_b"].code and top["photo_url"] == "/api/uploads/c.jpg"


def test_it_carries_the_remark_the_batch_and_the_models_guess(client, login_as, mill):
    login_as("owner")
    item = next(i for i in client.get("/api/qc/log").json()["items"] if i["remark"] == "Slub near the edge")
    assert item["lots"] == [mill["lot_1"].lot_code] and item["overrode_ai"] is True
    assert item["ai"]["verdict"] == "pass" and item["verdict"] == "rework"


def test_checks_without_a_photo_can_be_included(client, login_as, mill):
    login_as("owner")
    assert client.get("/api/qc/log?with_photo=false").json()["counts"]["total"] == 4


def test_filter_by_order_by_code_or_buyer_name(client, login_as, mill):
    login_as("owner")
    r1, r2, r3, _ = mill["rolls"]
    assert codes(client.get("/api/qc/log", params={"order": mill["order_a"].code}).json()) == [r2.code, r1.code]
    assert codes(client.get("/api/qc/log", params={"order": mill["order_b"].buyer.name}).json()) == [r3.code]
    assert codes(client.get("/api/qc/log", params={"order": "no such order"}).json()) == []


def test_filter_by_batch_is_the_yarn_lot_the_roll_was_woven_from(client, login_as, mill):
    login_as("owner")
    r1, r2, r3, _ = mill["rolls"]
    assert codes(client.get("/api/qc/log", params={"lot": mill["lot_2"].lot_code}).json()) == [r3.code]
    assert codes(client.get("/api/qc/log", params={"lot": mill["lot_1"].lot_code}).json()) == [r2.code, r1.code]
    assert codes(client.get("/api/qc/log", params={"lot": "LOT-9999"}).json()) == []


def test_filter_by_result_and_by_date(client, login_as, mill):
    login_as("owner")
    r1, r2, r3, _ = mill["rolls"]
    assert codes(client.get("/api/qc/log?verdict=reject").json()) == [r3.code]
    assert codes(client.get("/api/qc/log?date_from=2026-10-02&date_to=2026-10-04").json()) == [r2.code]
    assert codes(client.get("/api/qc/log?overrode_ai=true").json()) == [r2.code]
    assert codes(client.get("/api/qc/log?q=slub").json()) == [r2.code]


def test_paging_keeps_the_totals_for_the_whole_filter(client, login_as, mill):
    login_as("owner")
    page = client.get("/api/qc/log?limit=1&offset=1").json()
    assert len(page["items"]) == 1 and page["counts"]["total"] == 3 and (page["limit"], page["offset"]) == (1, 1)


def test_the_filter_lists_offer_only_orders_and_lots_that_have_checks(client, login_as, mill):
    login_as("owner")
    body = client.get("/api/qc/log/filters").json()
    assert {o["code"] for o in body["orders"]} == {mill["order_a"].code, mill["order_b"].code}
    assert set(body["lots"]) == {mill["lot_1"].lot_code, mill["lot_2"].lot_code}


@pytest.mark.parametrize("role,allowed", [("owner", True), ("qc", True), ("supervisor", True), ("accountant", False),
                                          ("store", False), ("dispatch", False), ("buyer", False)])
def test_who_may_see_the_log(client, login_as, mill, role, allowed):
    login_as(role)
    assert (client.get("/api/qc/log").status_code == 200) is allowed
    assert (client.get("/api/qc/log/filters").status_code == 200) is allowed


def test_a_visitor_who_is_not_logged_in_is_refused(client):
    assert client.get("/api/qc/log").status_code == 401


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "verdict=maybe", "date_from=yesterday"])
def test_bad_filters_are_422(client, login_as, query):
    login_as("owner")
    assert client.get(f"/api/qc/log?{query}").status_code == 422


def test_sorting_by_date_order_or_batch(client, login_as, mill):
    login_as("owner")
    r1, r2, r3, _ = mill["rolls"]
    assert codes(client.get("/api/qc/log?sort=oldest").json()) == [r1.code, r2.code, r3.code]
    assert codes(client.get("/api/qc/log?sort=order").json()) == [r2.code, r1.code, r3.code]   # ORD of A before B, newest first inside
    batch = codes(client.get("/api/qc/log?sort=batch").json())
    first_lot = min(mill["lot_1"].lot_code, mill["lot_2"].lot_code)
    expected_first = {r2.code, r1.code} if first_lot == mill["lot_1"].lot_code else {r3.code}
    assert set(batch[: len(expected_first)]) == expected_first
    assert client.get("/api/qc/log?sort=colour").status_code == 422
