"""B7: the delivery date, late orders, shortages and root causes through the API, on hand-worked mills
(tests/insights_world.py). Dates are relative to today."""
import datetime as dt

import pytest
from app.config import settings
from app.db.models import MachineDowntime, YarnMovement
from tests.factories import make_machine, make_order, make_roll, make_run
from tests.insights_world import build_defect_mill, build_mill

DAY = dt.timedelta(days=1)


@pytest.fixture
def mill(db):
    return build_mill(db)


def test_a_late_order_has_a_delivery_date_a_bottleneck_and_stage_dates(client, login_as, mill):
    login_as("owner")
    body = client.get(f"/api/orders/{mill.order_a.code}/eta").json()
    t = mill.today
    assert (body["delivery_date"], body["days_late"], body["bottleneck_stage"]) == (str(t + 4 * DAY), 1, "weaving")
    assert body["buyer_name"] == "Sharma Fabrics" and body["deadline"] == str(t + 3 * DAY)
    assert [(s["stage"], s["finish_date"]) for s in body["stages"]] == [
        ("spinning", str(t + DAY)), ("weaving", str(t + 2 * DAY)), ("dyeing", str(t + 2 * DAY))]
    assert body["what_ifs"] == []                                  # all three shifts already run; and A is already first


def test_an_order_on_time_has_no_bottleneck(client, login_as, mill):
    login_as("owner")
    body = client.get(f"/api/orders/{mill.order_b.code}/eta").json()
    assert (body["delivery_date"], body["days_late"], body["bottleneck_stage"], body["what_ifs"]) == (
        str(mill.today + 6 * DAY), 0, None, [])


def test_an_extra_shift_what_if_appears_when_weaving_runs_two_of_three_shifts(client, login_as, mill, monkeypatch):
    monkeypatch.setattr(settings, "stage_shifts", "weaving=2")
    login_as("owner")
    body = client.get(f"/api/orders/{mill.order_a.code}/eta").json()
    assert (body["delivery_date"], body["days_late"]) == (str(mill.today + 5 * DAY), 2)        # 480 m at 160 m a day
    assert body["what_ifs"] == [{"kind": "add_shift", "label": "Add a third shift on weaving",
                                 "delivery_date": str(mill.today + 4 * DAY), "days_late": 1}]


def test_late_orders_lists_only_the_late_ones(client, login_as, mill):
    login_as("owner")
    late = client.get("/api/insights/late-orders").json()
    assert [(o["order_code"], o["days_late"]) for o in late] == [(mill.order_a.code, 1)]


def test_the_order_list_and_detail_carry_the_real_dates(client, login_as, mill, db):
    draft = make_order(db, buyer=mill.buyer, fabric_type=mill.fabric, state="draft")
    login_as("owner")
    rows = {o["code"]: o for o in client.get("/api/orders").json()}
    assert (rows[mill.order_a.code]["delivery_date"], rows[mill.order_a.code]["days_late"]) == (str(mill.today + 4 * DAY), 1)
    assert (rows[mill.order_b.code]["delivery_date"], rows[mill.order_b.code]["days_late"]) == (str(mill.today + 6 * DAY), 0)
    assert (rows[draft.code]["delivery_date"], rows[draft.code]["days_late"]) == (None, None)       # not waiting for production
    one = client.get(f"/api/orders/{mill.order_a.code}").json()
    assert (one["delivery_date"], one["days_late"]) == (str(mill.today + 4 * DAY), 1)


def test_an_order_not_waiting_for_production_is_a_409(client, login_as, mill, db):
    draft = make_order(db, buyer=mill.buyer, fabric_type=mill.fabric, state="draft")
    login_as("owner")
    response = client.get(f"/api/orders/{draft.code}/eta")
    assert response.status_code == 409 and response.json()["code"] == "NOT_SCHEDULED"
    assert client.get("/api/orders/ORD-9999/eta").status_code == 404


def test_no_working_machine_at_a_stage_with_work_is_a_409_and_a_null_date(client, login_as, mill, db):
    db.add(MachineDowntime(machine_id=mill.machines["weaving"].id, reason="belt snapped"))
    db.flush()
    login_as("owner")
    response = client.get(f"/api/orders/{mill.order_a.code}/eta")
    assert response.status_code == 409 and response.json()["code"] == "NO_CAPACITY" and "weaving" in response.json()["message"]
    assert client.get(f"/api/orders/{mill.order_a.code}").json()["delivery_date"] is None
    assert client.get("/api/insights/late-orders").json() == []


def test_the_shortage_forecast_for_cotton(client, login_as, mill):
    """100 kg on hand, level 50, supplier lead time 4 days; both orders draw 240 kg within their first day:
    free = 100 - 480 = -380, below the level today, order by 4 days ago, 4 days overdue, suggest 50 + 380 = 430 -> 450 kg."""
    login_as("owner")
    rows = client.get("/api/insights/shortages").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["yarn_type"]["id"] == mill.cotton.id and row["supplier"] == {"id": mill.supplier.id, "name": "Vardhman Yarns"}
    assert (row["free_kg"], row["reorder_level_kg"], row["suggested_kg"], row["overdue_days"]) == (-380.0, 50.0, 450.0, 4)
    assert (row["falls_below_on"], row["order_by"]) == (str(mill.today), str(mill.today - 4 * DAY))


def test_a_blocked_lot_leaves_stock_and_raises_a_shortage_that_was_not_there(client, login_as, mill, db):
    db.add(YarnMovement(yarn_lot_id=mill.lot.id, kind="receipt", qty_kg=1000, moved_by=mill.lot.received_by))
    db.flush()                                                                         # 1,100 kg on hand covers the 480 kg needed
    login_as("owner")
    assert client.get("/api/insights/shortages").json() == []
    mill.lot.is_blocked, mill.lot.blocked_reason, mill.lot.blocked_at = True, "colour fault", dt.datetime.now(dt.UTC)
    db.flush()
    assert len(client.get("/api/insights/shortages").json()) == 1                      # a blocked lot is not stock


def test_root_causes_flag_the_group_that_is_unlikely_to_be_chance(client, login_as, db):
    world = build_defect_mill(db)
    login_as("supervisor")
    rows = client.get("/api/insights/root-causes").json()
    assert [(r["factor"], r["value"]) for r in rows] == [
        ("weaving_machine", world.loom_a.code), ("dyeing_machine", world.dyer.code), ("weaving_operator", "Operator 1"),
        ("weaving_shift", "Night"), ("yarn_lot", world.lot_a.lot_code)]
    for row in rows:
        assert (row["defective"], row["inspected"], row["rate"], row["rest_rate"], row["flagged"]) == (6, 10, 0.6, 0.0, True)
        assert row["p_value"] == pytest.approx(1001 / 184756)


def _recent_weaving_run(db, mill, ended_hours_ago, roll_metres):
    """A finished order whose weaving run took 5 hours and ended `ended_hours_ago` hours ago, making one roll."""
    done = make_order(db, state="cancelled")
    now = dt.datetime.now(dt.UTC)
    hours = dt.timedelta(hours=1)
    spin = make_run(db, done, mill.machines["spinning"], started_at=now - ended_hours_ago * hours - 6 * hours,
                    ended_at=now - ended_hours_ago * hours - 5 * hours)
    weave = make_run(db, done, mill.machines["weaving"], input_run_id=spin.id, started_at=now - ended_hours_ago * hours - 5 * hours,
                     ended_at=now - ended_hours_ago * hours)
    make_roll(db, done, weave, roll_metres)


def test_a_recent_slow_run_lowers_the_weaving_capacity(client, login_as, mill, db):
    """25 m in 5 hours on a loom rated 12.5 m/h is efficiency 25 / (12.5 x 5) = 0.4, so weaving makes 12.5 x 0.4 x 24 =
    120 m a day, not 240: order A's 480 m take 4 days, delivery today + 4 + 2, 3 days late."""
    _recent_weaving_run(db, mill, ended_hours_ago=1, roll_metres=25)
    login_as("owner")
    body = client.get(f"/api/orders/{mill.order_a.code}/eta").json()
    assert (body["delivery_date"], body["days_late"], body["bottleneck_stage"]) == (str(mill.today + 6 * DAY), 3, "weaving")


def test_a_run_that_ended_before_the_efficiency_window_is_ignored(client, login_as, mill, db):
    _recent_weaving_run(db, mill, ended_hours_ago=10 * 24, roll_metres=25)                      # ten days ago, window is seven
    login_as("owner")
    assert client.get(f"/api/orders/{mill.order_a.code}/eta").json()["delivery_date"] == str(mill.today + 4 * DAY)


def test_root_causes_are_empty_when_nothing_has_been_inspected(client, login_as, db):
    login_as("owner")
    assert client.get("/api/insights/root-causes").json() == []
    assert client.get("/api/insights/shortages").json() == []
    assert client.get("/api/insights/late-orders").json() == []


@pytest.mark.parametrize("role", ["store", "dispatch", "qc", "buyer"])
def test_planners_only(client, login_as, mill, role):
    login_as(role)
    for path in (f"/api/orders/{mill.order_a.code}/eta", "/api/insights/late-orders", "/api/insights/root-causes"):
        assert client.get(path).status_code == 403
    assert client.get("/api/insights/shortages").status_code == (200 if role == "store" else 403)
