"""B6: the month report on the hand-worked September 2026 mill (tests/costing_world.py)."""
import datetime as dt

import pytest
from app.db.models import BuyerPayment, SupplierPayment, WagePayment
from tests.costing_world import build_world
from tests.test_llm_api import Fake, use


@pytest.fixture
def world(db):
    return build_world(db)


def test_the_month_report_matches_the_hand_worked_september(client, login_as, db, world):
    # payments dated in October must not leak into September's cash, or into its outstanding amounts
    db.add(BuyerPayment(invoice_id=world.invoice.id, amount=7, received_at=dt.date(2026, 10, 1)))
    db.add(SupplierPayment(bill_id=world.bill.id, amount=9, paid_at=dt.date(2026, 10, 2)))
    db.add(WagePayment(worker_id=world.workers["ravi"].id, period_start=dt.date(2026, 10, 1),
                       period_end=dt.date(2026, 10, 31), amount=11, paid_at=dt.date(2026, 10, 3)))
    db.flush()
    login_as("owner")
    body = client.get("/api/reports/month?month=2026-09").json()
    assert body["month"] == "2026-09"
    assert body["profit"] == {
        "invoiced": 50000.0, "yarn_issued": 25000.0, "wages_earned": 2500.0, "idle_labour": 850.0,
        "support_staff": 800.0, "machine_running_cost": 640.0, "stock_writeoffs": 500.0, "profit": 21360.0,
    }
    assert body["cash"] == {
        "received_from_buyers": 20000.0, "paid_to_suppliers": 40000.0, "paid_wages": 1000.0, "net_cash": -21000.0,
        "receivables_outstanding": 30000.0, "payables_outstanding": 60000.0,
    }
    assert body["orders"] == [{"order_code": world.order.code, "buyer_name": "Sharma Fabrics", "revenue": 50000.0,
                               "cost": 26490.0, "profit": 23510.0}]
    p = body["profit"]            # the reconciliation invariant, on the rounded figures the page shows
    assert body["orders"][0]["cost"] + p["idle_labour"] + p["support_staff"] == p["yarn_issued"] + p["wages_earned"] + p["machine_running_cost"]


def test_the_month_machines_count_only_shift_time(client, login_as, world):
    login_as("owner")
    machines = {m["stage"]: m for m in client.get("/api/reports/month?month=2026-09").json()["machines"]}
    # the only shift is 06:00-14:00, so September has 30 x 8 = 240 hours of shift time
    assert (machines["spinning"]["running_h"], machines["spinning"]["idle_h"], machines["spinning"]["down_h"]) == (4.0, 236.0, 0.0)
    assert (machines["spinning"]["output"], machines["spinning"]["output_unit"]) == (95.0, "kg")
    assert (machines["spinning"]["lost_capacity"], machines["spinning"]["lost_capacity_unit"]) == (4720.0, "kg")
    assert (machines["weaving"]["running_h"], machines["weaving"]["output"], machines["weaving"]["lost_capacity"]) == (4.0, 1000.0, 6608.0)
    assert (machines["dyeing"]["running_h"], machines["dyeing"]["idle_h"], machines["dyeing"]["output"]) == (0.0, 240.0, 1000.0)
    assert machines["dyeing"]["lost_capacity"] == 10800.0


def test_the_month_report_warns_about_a_run_with_no_attendance(client, login_as, world):
    login_as("owner")
    warnings = client.get("/api/reports/month?month=2026-09").json()["warnings"]
    assert len(warnings) == 1 and f"Run {world.runs['dye'].id} " in warnings[0]


def test_the_month_wages_equal_the_wages_page_total(client, login_as, world):
    login_as("accountant")
    page = client.get("/api/wages?month=2026-09").json()["total_earned"]
    assert client.get("/api/reports/month?month=2026-09").json()["profit"]["wages_earned"] == page == 2500.0


def test_a_month_with_nothing_in_it_and_a_future_month_are_zeros_not_errors(client, login_as, world):
    login_as("owner")
    for month in ("2026-08", "2099-01"):
        body = client.get(f"/api/reports/month?month={month}").json()
        assert body["orders"] == [] and body["profit"]["profit"] == 0.0 and body["profit"]["invoiced"] == 0.0
        assert body["cash"]["net_cash"] == 0.0
    assert client.get("/api/reports/month?month=2026-08").json()["machines"] == []         # created after that month


@pytest.mark.parametrize("month", ["2026-13", "2026-00", "26-09", "september", "2026-9"])
def test_a_bad_month_is_a_422(client, login_as, month):
    login_as("owner")
    assert client.get(f"/api/reports/month?month={month}").status_code == 422


@pytest.mark.parametrize("month", ["0000-01", "0001-01", "1899-12", "2101-01", "9999-12"])
def test_a_month_outside_1900_to_2100_is_a_clean_422_not_a_crash(client, login_as, month):
    login_as("owner")
    response = client.get(f"/api/reports/month?month={month}")
    assert response.status_code == 422 and response.json()["field"] == "month"


@pytest.mark.parametrize("month", ["1900-01", "2100-12"])
def test_the_edge_months_are_allowed(client, login_as, month):
    login_as("owner")
    assert client.get(f"/api/reports/month?month={month}").status_code == 200


def test_the_assistants_month_summary_also_refuses_an_impossible_year_cleanly(client, login_as):
    """The assistant reads the month report through the same code, and its own month pattern allows 0000-01."""
    use(Fake("unused"))
    login_as("owner")
    response = client.post("/api/ai/month-summary", json={"month": "0000-01"})
    assert response.status_code == 422 and response.json()["field"] == "month"
