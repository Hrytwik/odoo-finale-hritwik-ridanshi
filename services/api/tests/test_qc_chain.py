"""B4 Task 6: B2, B3 and B4 together in one real chain through the API. A 1,000 m order (need 126 kg): spin, weave two
rolls (600 m and 400 m), dye, then quality control: roll A passes; roll B is sent back with 2 holes, mended, inspected
again and passes. After each step the order's progress and stage, the QC queue and the passport must agree."""
import datetime as dt

from app.core.auth import COOKIE_NAME, create_token
from tests.factories import (
    make_fabric_type, make_machine, make_supplier, make_user, make_worker, make_yarn_type,
)


def test_receive_to_passed_rolls_through_the_api(client, db, login_as):
    cotton = make_yarn_type(db, reorder_level_kg=10)
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.12, wastage_pct=5)
    supplier = make_supplier(db)
    spinner, loom, dyer = (make_machine(db, stage=s) for s in ("spinning", "weaving", "dyeing"))
    operator = make_worker(db)
    buyer_user = login_as("buyer")
    mine = buyer_user.buyer

    owner_user = make_user(db, role="owner")

    def order(code):
        """Read the order as the owner, whoever is logged in (a QC login cannot read orders), then restore the cookie."""
        before = client.cookies.get(COOKIE_NAME)
        client.cookies.set(COOKIE_NAME, create_token(owner_user.id))
        out = client.get(f"/api/orders/{code}").json()
        client.cookies.set(COOKIE_NAME, before)
        return out

    def queue():
        return client.get("/api/qc/queue").json()

    def statuses(code):
        return {r["code"]: r["status"] for r in client.get(f"/api/rolls?order_code={code}").json()}

    login_as("store")
    lot = client.post("/api/lots", json={"yarn_type_id": cotton.id, "supplier_id": supplier.id, "qty_kg": 200,
                                         "cost_per_kg": 250, "challan_no": "CH-QC"}).json()
    login_as("owner")
    created = client.post("/api/orders", json={"buyer_id": mine.id, "fabric_type_id": fabric.id, "colour": "navy",
                                               "qty_metres": 1000, "price_per_metre": 120,
                                               "deadline": str(dt.date.today() + dt.timedelta(days=30))})
    assert created.status_code == 201, created.text
    code = created.json()["code"]
    client.post(f"/api/orders/{code}/confirm")
    assert order(code)["progress"]["need_kg"] == 126.0

    login_as("supervisor")
    spin = client.post("/api/runs", json={"order_code": code, "machine_code": spinner.code,
                                          "operator_worker_id": operator.id}).json()
    login_as("store")
    assert client.post("/api/movements/issue", json={"lot_code": lot["lot_code"], "run_id": spin["id"],
                                                     "qty_kg": 120}).status_code == 201
    login_as("supervisor")
    assert client.post(f"/api/runs/{spin['id']}/end", json={"output_kg": 118}).status_code == 200
    weave = client.post("/api/runs", json={"order_code": code, "machine_code": loom.code,
                                           "operator_worker_id": operator.id, "input_run_id": spin["id"]}).json()
    roll_a = client.post(f"/api/runs/{weave['id']}/rolls", json={"metres": 600}).json()["code"]
    roll_b = client.post(f"/api/runs/{weave['id']}/rolls", json={"metres": 400}).json()["code"]
    dye = client.post("/api/runs", json={"order_code": code, "machine_code": dyer.code,
                                         "operator_worker_id": operator.id}).json()
    assert client.post(f"/api/runs/{dye['id']}/load-rolls", json={"roll_codes": [roll_a, roll_b]}).status_code == 200
    assert client.post(f"/api/runs/{dye['id']}/end", json={}).status_code == 200

    # quality control: both rolls wait
    login_as("qc")
    assert queue()["counts"] == {"awaiting_qc": 2, "awaiting_rework": 0, "in_rework": 0, "passed": 0, "rejected": 0}
    assert {r["code"] for r in queue()["rolls"]} == {roll_a, roll_b}
    assert order(code)["stage"] == "quality_check"

    # roll A passes
    assert client.post("/api/qc/inspections", json={"roll_code": roll_a, "verdict": "pass", "defects": []}).status_code == 201
    assert order(code)["progress"]["passed_m"] == 600.0 and order(code)["stage"] == "quality_check"

    # roll B is sent back with two holes
    sent = client.post("/api/qc/inspections", json={"roll_code": roll_b, "verdict": "rework",
                                                    "defects": [{"defect_type": "hole", "count": 2}]})
    assert sent.status_code == 201 and statuses(code)[roll_b] == "awaiting_rework"
    assert queue()["counts"]["awaiting_rework"] == 1 and queue()["counts"]["passed"] == 1

    # mended by hand, then back to QC
    login_as("supervisor")
    mend = client.post("/api/rework-runs", json={"roll_code": roll_b, "operator_worker_id": operator.id})
    assert mend.status_code == 201 and statuses(code)[roll_b] == "in_rework"
    login_as("qc")
    assert queue()["counts"]["in_rework"] == 1
    login_as("supervisor")
    assert client.post(f"/api/runs/{mend.json()['id']}/end", json={}).status_code == 200
    assert statuses(code)[roll_b] == "awaiting_qc"
    login_as("qc")
    assert client.post("/api/qc/inspections", json={"roll_code": roll_b, "verdict": "pass", "defects": []}).status_code == 201

    # everything passed: ready to ship
    out = order(code)
    assert out["progress"]["passed_m"] == 1000.0 and out["stage"] == "ready_to_ship"
    assert queue()["counts"] == {"awaiting_qc": 0, "awaiting_rework": 0, "in_rework": 0, "passed": 2, "rejected": 0}
    assert queue()["rolls"] == [] and set(statuses(code).values()) == {"in_store"}

    # the passport of the reworked roll tells the whole story
    login_as("owner")
    p = client.get(f"/api/rolls/{roll_b}/passport").json()
    assert [r["stage"] for r in p["runs"]] == ["spinning", "weaving", "dyeing", "rework"]
    assert [l["lot_code"] for l in p["yarn_lots"]] == [lot["lot_code"]]
    assert [(i["verdict"], [d["defect_type"] for d in i["defects"]]) for i in p["inspections"]] == [
        ("rework", ["hole"]), ("pass", [])]
    assert p["roll"]["status"] == "in_store" and p["cost"]["roll_code"] == roll_b and p["dispatch"] is None

    # the buyer of the order sees their own roll, reduced; a roll that does not exist is a 404
    client.cookies.set(COOKIE_NAME, create_token(buyer_user.id))        # the order's own buyer (login_as would make a new one)
    seen = client.get(f"/api/rolls/{roll_b}/passport")
    assert seen.status_code == 200 and seen.json()["runs"] == [] and seen.json()["yarn_lots"] == []
    assert all(i["inspector"]["name"] == "Quality team" for i in seen.json()["inspections"])
    assert client.get("/api/rolls/R-9999999/passport").status_code == 404
