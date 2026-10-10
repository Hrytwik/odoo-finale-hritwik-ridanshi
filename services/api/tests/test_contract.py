from app.main import app


def test_openapi_lists_core_paths():
    paths = app.openapi()["paths"]
    for p in ["/api/health", "/api/auth/login", "/api/auth/me", "/api/uploads", "/api/events"]:
        assert p in paths


EXPECTED = [
    "/api/suppliers", "/api/buyers", "/api/yarn-types", "/api/fabric-types", "/api/machines", "/api/workers",
    "/api/shifts", "/api/users", "/api/lots", "/api/lots/{lot_code}/recall", "/api/movements/issue", "/api/stock",
    "/api/orders", "/api/orders/{order_code}/yarn-check", "/api/floor", "/api/runs", "/api/runs/{run_id}/rolls",
    "/api/machines/{machine_code}/breakdown", "/api/qc/queue", "/api/qc/analyze", "/api/qc/inspections",
    "/api/rework-runs", "/api/qc/model-card", "/api/rolls/{roll_code}/passport", "/api/dispatches",
    "/api/dispatches/{dispatch_code}/confirm", "/api/invoices/{invoice_no}", "/api/money/receivables",
    "/api/payments/supplier", "/api/costing/orders/{order_code}", "/api/reports/month",
    "/api/insights/late-orders", "/api/orders/{order_code}/eta", "/api/insights/shortages",
    "/api/insights/root-causes", "/api/portal/orders", "/api/portal/orders/{order_code}",
]


def test_every_track_b_endpoint_in_spec_is_in_the_contract():
    paths = app.openapi()["paths"]
    missing = [p for p in EXPECTED if p not in paths]
    assert missing == []
