"""B6: the costing endpoints on a hand-worked September 2026 mill (tests/costing_world.py).

Hand-worked (see docs/plans/B6-costing.md):
  yarn 100 kg x 250 = 25,000 | machine 4 h x 55 + 4 h x 60 + 2 h x 90 = 640 | labour: Ravi 400 + Suresh 450 = 850
  order cost 26,490; two rolls of 500 m, R2 rejected, so R1 carries all of it: 26,490 / 500 = 52.98 a metre."""
import datetime as dt

import pytest
from app.core.auth import COOKIE_NAME, create_token
from app.db.models import Attendance
from tests.costing_world import at, build_world
from tests.factories import (
    make_inspection, make_machine, make_order, make_roll, make_run, make_shift, make_user, make_worker,
)


@pytest.fixture
def world(db):
    return build_world(db)


def test_a_rolls_cost_carries_the_rejected_rolls_cost(client, login_as, world):
    login_as("owner")
    r1 = client.get(f"/api/costing/rolls/{world.r1.code}")
    assert r1.status_code == 200
    assert r1.json() == {
        "roll_code": world.r1.code, "parts": {"yarn": 12500.0, "machine": 320.0, "labour": 425.0, "rework": 0.0},
        "reject_share": 13245.0, "total": 26490.0, "per_metre": 52.98, "provisional": False,
    }
    r2 = client.get(f"/api/costing/rolls/{world.r2.code}").json()
    assert (r2["reject_share"], r2["total"], r2["per_metre"]) == (0.0, 13245.0, 26.49)


def test_an_orders_cost_breakdown(client, login_as, world):
    login_as("accountant")
    body = client.get(f"/api/costing/orders/{world.order.code}").json()
    assert body["parts"] == {"yarn": 25000.0, "machine": 640.0, "labour": 850.0, "rework": 0.0}
    assert (body["total"], body["reject_cost"], body["good_metres"], body["rejected_metres"]) == (26490.0, 13245.0, 500.0, 500.0)
    assert (body["cost_per_good_metre"], body["revenue"], body["profit"], body["unabsorbed"]) == (52.98, 50000.0, 23510.0, 0.0)
    assert body["provisional"] is False
    dye_run, dyer = world.runs["dye"], world.machines["dye"]
    assert body["warnings"] == [
        f"Run {dye_run.id} ({dyer.code}, 2026-09-03) has 2.0 hours not covered by its operator's attendance"]


def test_the_cost_is_provisional_while_a_run_is_still_open(client, login_as, db, world):
    make_run(db, world.order, world.machines["dye"], world.workers["lakshmi"], started_at=at(5, 6))
    login_as("owner")
    body = client.get(f"/api/costing/orders/{world.order.code}").json()
    assert body["provisional"] is True
    assert any("is still open" in w for w in body["warnings"])
    assert client.get(f"/api/costing/rolls/{world.r1.code}").json()["provisional"] is True


def test_unknown_roll_and_order_are_404(client, login_as, world):
    login_as("owner")
    assert client.get("/api/costing/rolls/R-9999").status_code == 404
    assert client.get("/api/costing/orders/ORD-9999").status_code == 404


@pytest.mark.parametrize("role", ["store", "supervisor", "qc", "dispatch", "buyer"])
def test_only_owner_and_accountant_may_read_cost(client, login_as, world, role):
    login_as(role)
    for path in (f"/api/costing/rolls/{world.r1.code}", f"/api/costing/orders/{world.order.code}", "/api/reports/month?month=2026-09"):
        assert client.get(path).status_code == 403


def test_the_passport_shows_cost_to_owner_and_accountant_only(client, login_as, db, world):
    for role in ("owner", "accountant"):
        login_as(role)
        assert client.get(f"/api/rolls/{world.r1.code}/passport").json()["cost"]["total"] == 26490.0
    for role in ("store", "supervisor", "qc", "dispatch"):
        login_as(role)
        assert client.get(f"/api/rolls/{world.r1.code}/passport").json()["cost"] is None


def test_a_buyer_never_sees_any_cost_even_for_their_own_roll(client, db, world):
    buyer = make_user(db, role="buyer", buyer_id=world.buyer.id)
    client.cookies.set(COOKIE_NAME, create_token(buyer.id))
    response = client.get(f"/api/rolls/{world.r1.code}/passport")
    assert response.status_code == 200 and response.json()["cost"] is None
    for giveaway in ('"per_metre"', '"reject_share"', '"parts"', '"machine"', '"labour"', '"yarn"', '"rework"',
                     "26490", "13245", "52.98"):                       # cost-shaped keys (quoted, so "yarn_lots" is not one) and amounts
        assert giveaway not in response.text




def test_an_order_with_no_runs_and_no_rolls_costs_nothing_and_divides_by_nothing(client, login_as, db):
    order = make_order(db, qty_metres=300, price_per_metre=100)
    login_as("owner")
    body = client.get(f"/api/costing/orders/{order.code}").json()
    assert body["parts"] == {"yarn": 0.0, "machine": 0.0, "labour": 0.0, "rework": 0.0}
    assert (body["total"], body["good_metres"], body["cost_per_good_metre"], body["revenue"], body["profit"]) \
        == (0.0, 0.0, None, 0.0, 0.0)
    assert body["provisional"] is True and body["warnings"] == []


def test_an_order_whose_only_roll_is_rejected_shows_everything_as_unabsorbed(client, login_as, db):
    order = make_order(db, qty_metres=100)
    weave = make_run(db, order, make_machine(db, stage="weaving", running_cost_per_hour=60),
                     started_at=at(3, 10), ended_at=at(3, 12))
    roll = make_roll(db, order, weave, 100)
    make_inspection(db, roll, "reject")
    login_as("owner")
    body = client.get(f"/api/costing/orders/{order.code}").json()
    assert (body["total"], body["cost_per_good_metre"], body["unabsorbed"], body["reject_cost"]) == (120.0, None, 120.0, 120.0)
    assert client.get(f"/api/costing/rolls/{roll.code}").json()["per_metre"] == 1.2          # its own cost, 120 / 100 m


def test_a_workers_pay_is_shared_across_the_runs_of_different_orders(client, login_as, db):
    """One weaver minds two looms for 8 hours each, on two different orders: H = 16 against 8 paid hours, so each run
    gets 800 x 8/16 = 400. An order costed on its own would see only 8 hours and charge itself the whole 800."""
    shift = make_shift(db, name="A")
    marker = make_user(db, role="supervisor")
    weaver = make_worker(db, role="operator", daily_wage=800)
    db.add(Attendance(worker_id=weaver.id, work_date=dt.date(2026, 9, 3), shift_id=shift.id, status="present",
                      marked_by=marker.id))
    orders = [make_order(db), make_order(db)]
    for order in orders:
        make_run(db, order, make_machine(db, stage="spinning", running_cost_per_hour=0), weaver,
                 started_at=at(3, 6), ended_at=at(3, 14))
    login_as("owner")
    for order in orders:
        assert client.get(f"/api/costing/orders/{order.code}").json()["parts"]["labour"] == 400.0
