def test_buyer_sees_portal(client, login_as):
    login_as("buyer")
    assert client.get("/api/portal/orders").status_code == 200
    detail = client.get("/api/portal/orders/ORD-0012").json()
    assert detail["timeline"] and detail["stage"]


def test_staff_cannot_use_portal(client, login_as):
    login_as("owner")
    assert client.get("/api/portal/orders").status_code == 403
