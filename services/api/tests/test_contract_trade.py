import pytest


@pytest.mark.parametrize("role,path", [
    ("accountant", "/api/money/receivables"), ("accountant", "/api/money/payables"),
    ("owner", "/api/reports/month?month=2026-10"),
    ("owner", "/api/insights/late-orders"), ("supervisor", "/api/orders/ORD-0012/eta"),
    ("store", "/api/insights/shortages"), ("owner", "/api/insights/root-causes"),
])
def test_example_data_served(client, login_as, role, path):
    login_as(role)
    assert client.get(path).status_code == 200, path


@pytest.mark.parametrize("month", ["2026-13", "26-10", "october", ""])
def test_month_must_be_yyyy_mm(client, login_as, month):
    login_as("owner")
    assert client.get(f"/api/reports/month?month={month}").status_code == 422


def test_payment_amount_must_be_positive(client, login_as):
    login_as("accountant")
    body = {"invoice_no": "INV-0007", "amount": -10, "received_on": "2026-10-10"}
    assert client.post("/api/payments/buyer", json=body).status_code == 422


def test_dispatch_needs_vehicle(client, login_as):
    login_as("dispatch")
    assert client.post("/api/dispatches", json={"buyer_id": 1, "vehicle_no": " "}).status_code == 422


def test_month_report_profit_arithmetic_is_consistent(client, login_as):
    login_as("owner")
    p = client.get("/api/reports/month?month=2026-10").json()["profit"]
    expected = p["invoiced"] - p["yarn_issued"] - p["wages_earned"] - p["machine_running_cost"] - p["stock_writeoffs"]
    assert abs(p["profit"] - expected) < 0.01


def test_buyer_cannot_use_staff_money_endpoints(client, login_as):
    login_as("buyer")
    assert client.get("/api/money/receivables").status_code == 403
