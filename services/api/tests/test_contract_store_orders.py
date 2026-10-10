def test_recall_is_still_example_data_until_b7(client, login_as):
    login_as("owner")
    r = client.get("/api/lots/L-0017/recall")
    assert r.status_code == 200 and r.json()["lot_code"] == "L-0017"


def test_adjustment_of_zero_rejected(client, login_as):
    login_as("store")
    r = client.post("/api/movements/adjust", json={"lot_code": "L-0017", "qty_kg": 0, "note": "count"})
    assert r.status_code == 422 and r.json()["field"] == "qty_kg"


def test_buyer_cannot_see_store(client, login_as):
    login_as("buyer")
    assert client.get("/api/stock").status_code == 403


def test_store_cannot_create_orders(client, login_as):
    login_as("store")
    r = client.post("/api/orders", json={"buyer_id": 1, "fabric_type_id": 1, "colour": "navy",
                                         "qty_metres": 1000, "price_per_metre": 120, "deadline": "2026-10-30"})
    assert r.status_code == 403
