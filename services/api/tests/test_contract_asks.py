import pytest

STAFF_ROLES = ["owner", "accountant", "store", "supervisor", "qc", "dispatch"]


# ---- 1. buyers must not receive internal data from the roll passport ------------------------

def _life_for(db, buyer=None):
    from tests.factories import make_inspection
    from tests.test_passport import Life

    life = Life(db, buyer=buyer)
    make_inspection(db, life.roll, "pass", photo_path="uploads/" + "ab12" * 8 + ".jpg",
                    ai_suggestion={"model_version": "yolo-1", "verdict": "pass", "boxes": []})
    return life


def test_a_buyer_never_receives_cost_lots_machines_or_operators(client, db, login_as):
    buyer_user = login_as("buyer")
    life = _life_for(db, buyer_user.buyer)
    p = client.get(f"/api/rolls/{life.roll.code}/passport").json()
    assert p["cost"] is None
    assert p["yarn_lots"] == []
    assert p["runs"] == []
    assert p["inspections"], "buyers still see the quality checks"
    for insp in p["inspections"]:
        assert insp["inspector"]["name"] == "Quality team"      # no person's name
        assert insp["ai_suggestion"] is None and insp["photo_url"] is None


def test_a_buyer_still_sees_status_order_and_dispatch(client, db, login_as):
    buyer_user = login_as("buyer")
    life = _life_for(db, buyer_user.buyer)
    p = client.get(f"/api/rolls/{life.roll.code}/passport").json()
    assert p["roll"]["status"] and p["order_code"] and p["deadline"]


@pytest.mark.parametrize("role", STAFF_ROLES)
def test_staff_keep_the_full_passport(client, db, login_as, role):
    login_as(role)
    life = _life_for(db)
    p = client.get(f"/api/rolls/{life.roll.code}/passport").json()
    assert p["yarn_lots"] and p["runs"]              # cost is empty until costing (B6)


def test_the_buyer_response_text_contains_no_secrets(client, db, login_as):
    buyer_user = login_as("buyer")
    life = _life_for(db, buyer_user.buyer)
    text = client.get(f"/api/rolls/{life.roll.code}/passport").text
    assert life.roll.code in text                    # a real passport, not an error page
    secrets = [life.supplier.name, life.spin.operator.name, life.weave.operator.name, life.loom.code,
               life.spin_machine.code, life.lot.lot_code, "per_metre", "uploads/", "yolo-1"]
    for secret in secrets:
        assert secret not in text, secret


# ---- 2. list rolls ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", STAFF_ROLES)
def test_staff_can_list_rolls(client, login_as, role):
    login_as(role)
    r = client.get("/api/rolls")
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_rolls_filter_by_status_and_order(client, db, login_as):
    from tests.factories import make_machine, make_order, make_roll, make_run

    login_as("dispatch")
    order = make_order(db)
    roll = make_roll(db, order, make_run(db, order, make_machine(db, stage="weaving")))
    woven = client.get("/api/rolls", params={"status": "woven", "order_code": order.code}).json()
    assert [r["code"] for r in woven] == [roll.code] and all(r["status"] == "woven" for r in woven)
    assert client.get("/api/rolls", params={"status": "rejected", "order_code": order.code}).json() == []
    assert client.get("/api/rolls", params={"order_code": "ORD-9999"}).json() == []


def test_rolls_reject_an_unknown_status(client, login_as):
    login_as("supervisor")
    assert client.get("/api/rolls", params={"status": "shiny"}).status_code == 422


def test_buyers_cannot_list_rolls(client, login_as):
    login_as("buyer")
    assert client.get("/api/rolls").status_code == 403


# ---- 3. list runs ----------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["supervisor", "owner", "accountant"])
def test_staff_who_see_the_floor_can_list_runs(client, login_as, role):
    login_as(role)
    assert client.get("/api/runs").status_code == 200


def test_runs_filter_by_stage_and_order(client, db, login_as):
    from tests.factories import make_machine, make_order, make_run

    login_as("supervisor")
    order = make_order(db)
    spin = make_run(db, order, make_machine(db, stage="spinning"))
    make_run(db, order, make_machine(db, stage="weaving"), input_run_id=spin.id)
    spinning = client.get("/api/runs", params={"stage": "spinning", "order_code": order.code}).json()
    assert len(spinning) == 1 and spinning[0]["stage"] == "spinning" and spinning[0]["order_code"] == order.code
    assert client.get("/api/runs", params={"stage": "dyeing", "order_code": order.code}).json() == []
    assert client.get("/api/runs", params={"stage": "dyeing", "order_code": "ORD-9999"}).json() == []


def test_runs_reject_an_unknown_stage(client, login_as):
    login_as("supervisor")
    assert client.get("/api/runs", params={"stage": "knitting"}).status_code == 422


@pytest.mark.parametrize("role", ["buyer", "store", "qc", "dispatch"])
def test_other_roles_cannot_list_runs(client, login_as, role):
    login_as(role)
    assert client.get("/api/runs").status_code == 403


def test_posting_a_run_still_works_next_to_the_new_get(client, db, login_as):
    from tests.factories import make_machine, make_order, make_worker

    login_as("supervisor")
    order, machine, worker = make_order(db), make_machine(db, stage="spinning"), make_worker(db)
    r = client.post("/api/runs", json={"order_code": order.code, "machine_code": machine.code,
                                       "operator_worker_id": worker.id})
    assert r.status_code == 201
    listed = client.get("/api/runs", params={"order_code": order.code}).json()
    assert [x["id"] for x in listed] == [r.json()["id"]]
