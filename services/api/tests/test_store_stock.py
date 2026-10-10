"""B2 Task 4: GET /stock reads v_yarn_type_stock. Hand-worked numbers: on hand 212.5, outstanding 42.5 + 400, free -230."""
import pytest

from tests.factories import make_lot, make_yarn_type
from tests.test_stock_views import issue, scenario, second_order_needing_400, spinning_run


def row_for(rows, yarn_type):
    [row] = [r for r in rows if r["yarn_type"]["id"] == yarn_type.id]
    return row


def test_the_minus_230_scenario_through_the_endpoint(client, db, login_as):
    login_as("store")
    cotton, _, order, lot = scenario(db)
    issue(db, lot, spinning_run(db, order), 587.5)
    second_order_needing_400(db, cotton)
    r = client.get("/api/stock")
    assert r.status_code == 200, r.text
    row = row_for(r.json(), cotton)
    assert row["on_hand_kg"] == 212.5 and row["outstanding_kg"] == 442.5 and row["free_kg"] == -230.0
    assert row["reorder_level_kg"] == 300.0 and row["below_reorder"] is True
    assert row["yarn_type"]["code"] == cotton.code and row["yarn_type"]["colour"] == cotton.colour


def test_a_yarn_type_without_lots_appears_with_zeros(client, db, login_as):
    login_as("owner")
    empty = make_yarn_type(db, reorder_level_kg=100)
    row = row_for(client.get("/api/stock").json(), empty)
    assert (row["on_hand_kg"], row["outstanding_kg"], row["free_kg"]) == (0.0, 0.0, 0.0)
    assert row["below_reorder"] is True and row["reorder_level_kg"] == 100.0


def test_rows_are_ordered_by_yarn_type_code(client, db, login_as):
    login_as("supervisor")
    made = [make_yarn_type(db, code=code) for code in ("ZZ-9", "AA-1", "MM-5")]
    codes = [r["yarn_type"]["code"] for r in client.get("/api/stock").json()]
    assert [c for c in codes if c in {y.code for y in made}] == ["AA-1", "MM-5", "ZZ-9"]


def test_quantities_keep_exactly_three_decimals(client, db, login_as):
    login_as("accountant")
    yarn = make_yarn_type(db, reorder_level_kg=0)
    make_lot(db, yarn_type=yarn, qty_kg=123.456)
    row = row_for(client.get("/api/stock").json(), yarn)
    assert row["on_hand_kg"] == 123.456 and row["free_kg"] == 123.456 and row["below_reorder"] is False


def test_a_blocked_lot_does_not_count_as_stock(client, db, login_as):
    import datetime as dt

    login_as("store")
    yarn = make_yarn_type(db, reorder_level_kg=0)
    make_lot(db, yarn_type=yarn, qty_kg=100)
    bad = make_lot(db, yarn_type=yarn, qty_kg=50)
    bad.is_blocked, bad.blocked_reason, bad.blocked_at = True, "damp", dt.datetime(2026, 10, 2, tzinfo=dt.UTC)
    db.flush()
    assert row_for(client.get("/api/stock").json(), yarn)["on_hand_kg"] == 100.0


@pytest.mark.parametrize("role", ["store", "owner", "supervisor", "accountant"])
def test_stock_readers(client, login_as, role):
    login_as(role)
    assert client.get("/api/stock").status_code == 200


@pytest.mark.parametrize("role", ["buyer", "qc", "dispatch"])
def test_other_roles_are_refused(client, login_as, role):
    login_as(role)
    assert client.get("/api/stock").status_code == 403
