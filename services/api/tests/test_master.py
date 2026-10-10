import pytest

from tests.factories import make_yarn_type


def test_owner_creates_and_lists_supplier(client, login_as):
    login_as("owner")
    r = client.post("/api/suppliers", json={"name": "  Vardhman Yarns ", "phone": "9800000000", "lead_time_days": 7})
    assert r.status_code == 201 and r.json()["name"] == "Vardhman Yarns"
    assert any(s["name"] == "Vardhman Yarns" for s in client.get("/api/suppliers").json())


def test_blank_name_is_422_with_field(client, login_as):
    login_as("owner")
    r = client.post("/api/suppliers", json={"name": "   ", "lead_time_days": 7})
    assert r.status_code == 422 and r.json()["field"] == "name"


def test_duplicate_name_is_409(client, login_as):
    login_as("owner")
    client.post("/api/buyers", json={"name": "Sharma Fabrics"})
    r = client.post("/api/buyers", json={"name": "Sharma Fabrics"})
    assert r.status_code == 409 and r.json()["code"] == "DUPLICATE" and r.json()["field"] == "name"


def test_staff_can_read_but_not_write(client, login_as):
    login_as("store")
    assert client.get("/api/yarn-types").status_code == 200
    assert client.post("/api/yarn-types", json={"code": "X", "name": "x", "colour": "y"}).status_code == 403


def test_buyer_cannot_read_master_data(client, login_as):
    login_as("buyer")
    assert client.get("/api/suppliers").status_code == 403


def test_not_logged_in_is_401(client):
    assert client.get("/api/suppliers").status_code == 401


def test_patch_updates_only_sent_fields(client, login_as):
    login_as("owner")
    created = client.post("/api/machines", json={
        "code": "LOOM-04", "name": "Loom 4", "stage": "weaving",
        "rated_output_per_hour": 22, "running_cost_per_hour": 60}).json()
    r = client.patch(f"/api/machines/{created['id']}", json={"active": False})
    assert r.status_code == 200 and r.json()["active"] is False and r.json()["name"] == "Loom 4"


def test_patch_missing_id_is_404(client, login_as):
    login_as("owner")
    assert client.patch("/api/machines/999999", json={"active": False}).status_code == 404


@pytest.mark.parametrize("bad", [
    {"rated_output_per_hour": 0}, {"rated_output_per_hour": -5}, {"stage": "knitting"},
])
def test_machine_bad_values_422(client, login_as, bad):
    login_as("owner")
    body = {"code": "M1", "name": "M", "stage": "weaving", "rated_output_per_hour": 10,
            "running_cost_per_hour": 10, **bad}
    assert client.post("/api/machines", json=body).status_code == 422


def test_fabric_type_with_recipe(client, login_as, db):
    login_as("owner")
    yt = make_yarn_type(db)
    r = client.post("/api/fabric-types", json={
        "name": "Poplin 58in", "width_in": 58, "wastage_pct": 5,
        "recipe": [{"yarn_type_id": yt.id, "kg_per_metre": 0.12}]})
    assert r.status_code == 201
    assert r.json()["recipe"][0]["yarn_type_code"] == yt.code


def test_fabric_type_needs_recipe_and_no_duplicate_yarns(client, login_as, db):
    login_as("owner")
    yt = make_yarn_type(db)
    base = {"name": "Twill", "width_in": 60, "wastage_pct": 5}
    assert client.post("/api/fabric-types", json={**base, "recipe": []}).status_code == 422
    dup = [{"yarn_type_id": yt.id, "kg_per_metre": 0.1}, {"yarn_type_id": yt.id, "kg_per_metre": 0.2}]
    assert client.post("/api/fabric-types", json={**base, "recipe": dup}).status_code == 422


def test_recipe_with_unknown_yarn_type_is_404(client, login_as):
    login_as("owner")
    r = client.post("/api/fabric-types", json={"name": "Ghost", "width_in": 60, "wastage_pct": 5,
                                               "recipe": [{"yarn_type_id": 999999, "kg_per_metre": 0.1}]})
    assert r.status_code == 404


def test_patching_the_recipe_replaces_it(client, login_as, db):
    login_as("owner")
    a, b = make_yarn_type(db), make_yarn_type(db)
    ft = client.post("/api/fabric-types", json={"name": "Denim", "width_in": 60, "wastage_pct": 5,
                                                "recipe": [{"yarn_type_id": a.id, "kg_per_metre": 0.2}]}).json()
    r = client.patch(f"/api/fabric-types/{ft['id']}", json={"recipe": [{"yarn_type_id": b.id, "kg_per_metre": 0.3}]})
    assert r.status_code == 200
    assert [(x["yarn_type_id"], x["kg_per_metre"]) for x in r.json()["recipe"]] == [(b.id, 0.3)]


def test_wastage_over_50_rejected(client, login_as, db):
    login_as("owner")
    yt = make_yarn_type(db)
    r = client.post("/api/fabric-types", json={"name": "T", "width_in": 60, "wastage_pct": 51,
                                               "recipe": [{"yarn_type_id": yt.id, "kg_per_metre": 0.1}]})
    assert r.status_code == 422


def test_user_create_hashes_password_and_validates_links(client, login_as):
    login_as("owner")
    buyer = client.post("/api/buyers", json={"name": "Patel Textiles"}).json()
    ok = client.post("/api/users", json={"username": "patel", "password": "secret12", "role": "buyer",
                                          "buyer_id": buyer["id"]})
    assert ok.status_code == 201 and "password" not in ok.json() and "password_hash" not in ok.json()
    bad = client.post("/api/users", json={"username": "nobuyer", "password": "secret12", "role": "buyer"})
    assert bad.status_code == 422


def test_created_user_can_log_in(client, login_as):
    login_as("owner")
    client.post("/api/users", json={"username": "newowner", "password": "secret12", "role": "owner"})
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"username": "newowner", "password": "secret12"}).status_code == 200


def test_only_owner_can_list_users(client, login_as):
    login_as("accountant")
    assert client.get("/api/users").status_code == 403


def test_user_password_over_72_bytes_is_422_not_500(client, login_as):
    login_as("owner")
    r = client.post("/api/users", json={"username": "longpw", "password": "é" * 40, "role": "owner"})
    assert r.status_code == 422 and r.json()["field"] == "password"


def test_shift_start_equals_end_rejected(client, login_as):
    login_as("owner")
    r = client.post("/api/shifts", json={"name": "Z", "start_time": "06:00", "end_time": "06:00"})
    assert r.status_code == 422


def test_patching_a_required_field_to_null_is_422_not_500(client, login_as):
    login_as("owner")
    b = client.post("/api/buyers", json={"name": "Null Test"}).json()
    r = client.patch(f"/api/buyers/{b['id']}", json={"name": None})
    assert r.status_code == 422, r.text


def test_patch_to_another_records_unique_value_is_409(client, login_as):
    login_as("owner")
    client.post("/api/buyers", json={"name": "First"})
    second = client.post("/api/buyers", json={"name": "Second"}).json()
    r = client.patch(f"/api/buyers/{second['id']}", json={"name": "First"})
    assert r.status_code == 409 and r.json()["field"] == "name"


def test_session_is_usable_after_a_rejected_write(client, login_as):
    login_as("owner")
    client.post("/api/buyers", json={"name": "Dup"})
    assert client.post("/api/buyers", json={"name": "Dup"}).status_code == 409
    assert client.post("/api/buyers", json={"name": "Other"}).status_code == 201


def test_shift_patch_that_makes_times_equal_is_rejected_cleanly(client, login_as):
    login_as("owner")
    s = client.post("/api/shifts", json={"name": "A", "start_time": "06:00", "end_time": "14:00"}).json()
    r = client.patch(f"/api/shifts/{s['id']}", json={"end_time": "06:00"})
    assert r.status_code == 422 and r.json()["code"] == "INVALID_VALUE", r.text
