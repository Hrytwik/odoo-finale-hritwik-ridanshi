"""B7: the recall chain (spec 8.4) on the hand-worked lot in tests/insights_world.py."""
import pytest
from tests.factories import make_lot
from tests.insights_world import build_recall_mill


@pytest.fixture
def mill(db):
    return build_recall_mill(db)


def codes(rows):
    return [r["roll_code"] for r in rows]


def test_the_lot_is_traced_to_every_roll_and_grouped_by_where_it_is(client, login_as, mill):
    login_as("store")
    body = client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()
    r = {key: roll.code for key, roll in mill.rolls.items()}
    assert body["lot_code"] == mill.lot.lot_code and body["is_blocked"] is False
    assert codes(body["on_floor"]) == sorted([r["R1"], r["R6"]])                       # R6 is rejected but still in the mill
    assert codes(body["in_store"]) == sorted([r["R2"], r["R3"]])
    assert codes(body["loading"]) == [r["R5"]] and codes(body["dispatched"]) == [r["R4"]]
    assert r["R7"] not in codes(body["on_floor"] + body["in_store"] + body["loading"] + body["dispatched"])   # S2 netted to zero
    assert {x["roll_code"]: x["status"] for x in body["on_floor"]} == {r["R1"]: "dyeing", r["R6"]: "rejected"}
    assert body["loading"][0]["dispatch_code"] == mill.loading_truck.code and body["dispatched"][0]["dispatch_code"] == mill.sent_truck.code
    assert body["in_store"][0]["dispatch_code"] is None and body["dispatched"][0]["buyer_name"] == "Sharma Fabrics"


def test_the_buyers_are_counted_with_only_confirmed_trucks_listed(client, login_as, mill):
    login_as("owner")
    buyers = {b["buyer_name"]: b for b in client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()["buyers"]}
    assert buyers["Sharma Fabrics"]["roll_count"] == 5 and buyers["Sharma Fabrics"]["dispatched_roll_count"] == 1
    assert buyers["Sharma Fabrics"]["dispatch_codes"] == [mill.sent_truck.code]
    assert buyers["Kavya Garments"]["roll_count"] == 1 and buyers["Kavya Garments"]["dispatched_roll_count"] == 0
    assert buyers["Kavya Garments"]["dispatch_codes"] == []                            # her truck has not left yet


def test_blocking_the_lot_changes_the_flag_but_not_the_rolls(client, login_as, mill):
    login_as("store")
    before = client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()
    assert client.post(f"/api/lots/{mill.lot.lot_code}/block", json={"reason": "colour fault"}).status_code == 200
    after = client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()
    assert after["is_blocked"] is True and {k: v for k, v in after.items() if k != "is_blocked"} == {k: v for k, v in before.items() if k != "is_blocked"}


def test_a_lot_nobody_used_has_nothing_to_recall_and_an_unknown_lot_is_a_404(client, login_as, db, mill):
    unused = make_lot(db)
    login_as("owner")
    body = client.get(f"/api/lots/{unused.lot_code}/recall").json()
    assert body["on_floor"] == body["in_store"] == body["loading"] == body["dispatched"] == body["buyers"] == []
    assert client.get("/api/lots/L-9999/recall").status_code == 404


@pytest.mark.parametrize("role", ["supervisor", "accountant", "qc", "dispatch", "buyer"])
def test_only_store_and_owner_may_read_a_recall(client, login_as, mill, role):
    login_as(role)
    assert client.get(f"/api/lots/{mill.lot.lot_code}/recall").status_code == 403


def test_the_recall_and_the_passport_agree_about_which_rolls_used_the_lot(client, login_as, mill):
    """A roll is in the lot's recall exactly when the roll's passport lists the lot."""
    login_as("owner")
    in_recall = set()
    body = client.get(f"/api/lots/{mill.lot.lot_code}/recall").json()
    for group in ("on_floor", "in_store", "loading", "dispatched"):
        in_recall |= set(codes(body[group]))
    for roll in mill.rolls.values():
        lots = [lot["lot_code"] for lot in client.get(f"/api/rolls/{roll.code}/passport").json()["yarn_lots"]]
        assert (mill.lot.lot_code in lots) == (roll.code in in_recall), roll.code
