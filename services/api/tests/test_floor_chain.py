"""B3 Task 7: one real chain through the API, B2 and B3 together. Receive 800 kg at 250 -> confirm a 5,000 m order
(need 630 kg) -> spin (issue 587.5 kg, end with 590 kg) -> weave (3 rolls = 2,310 m, with a hand-over in between)
-> dye (load the rolls, end the run) -> the order waits for quality check. After each step the order's progress,
stage and the stock numbers must say the same thing the floor board says."""
import datetime as dt

from tests.factories import (
    make_buyer, make_fabric_type, make_machine, make_supplier, make_worker, make_yarn_type,
)


def test_receive_to_dyed_rolls_through_the_api(client, db, login_as):
    cotton = make_yarn_type(db, reorder_level_kg=300)
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.12, wastage_pct=5)
    supplier, buyer = make_supplier(db), make_buyer(db)
    spinner = make_machine(db, stage="spinning")
    loom = make_machine(db, stage="weaving")
    dyer = make_machine(db, stage="dyeing")
    first, second = make_worker(db), make_worker(db)

    def order(code):
        r = client.get(f"/api/orders/{code}")
        assert r.status_code == 200, r.text
        return r.json()

    def machine(m):
        return next(x for x in client.get("/api/floor").json()["machines"] if x["code"] == m.code)

    def on_hand():
        row = next(x for x in client.get("/api/stock").json() if x["yarn_type"]["id"] == cotton.id)
        return row["on_hand_kg"], row["outstanding_kg"]

    # 1. the store receives 800 kg at 250
    login_as("store")
    lot = client.post("/api/lots", json={"yarn_type_id": cotton.id, "supplier_id": supplier.id, "qty_kg": 800,
                                         "cost_per_kg": 250, "challan_no": "CH-CHAIN"})
    assert lot.status_code == 201, lot.text
    lot_code = lot.json()["lot_code"]

    # 2. the owner creates and confirms a 5,000 m order: need 630 kg
    login_as("owner")
    created = client.post("/api/orders", json={"buyer_id": buyer.id, "fabric_type_id": fabric.id, "colour": "navy",
                                               "qty_metres": 5000, "price_per_metre": 120,
                                               "deadline": str(dt.date.today() + dt.timedelta(days=30))})
    assert created.status_code == 201, created.text
    code = created.json()["code"]
    assert client.post(f"/api/orders/{code}/confirm").status_code == 200
    o = order(code)
    assert o["stage"] == "waiting_to_start" and o["yarn_status"] == "can_start"
    assert o["progress"]["need_kg"] == 630.0 and on_hand() == (800.0, 630.0)

    # 3. a supervisor starts spinning, the store issues 587.5 kg to that run
    login_as("supervisor")
    spin = client.post("/api/runs", json={"order_code": code, "machine_code": spinner.code,
                                          "operator_worker_id": first.id})
    assert spin.status_code == 201, spin.text
    spin_id = spin.json()["id"]
    assert order(code)["stage"] == "spinning" and machine(spinner)["status"] == "running"
    login_as("store")
    issued = client.post("/api/movements/issue", json={"lot_code": lot_code, "run_id": spin_id, "qty_kg": 587.5})
    assert issued.status_code == 201, issued.text
    assert on_hand() == (212.5, 42.5)                                   # outstanding = 630 - 587.5
    line = client.get(f"/api/orders/{code}/yarn-check").json()["lines"][0]
    assert (line["issued_kg"], line["outstanding_kg"]) == (587.5, 42.5)

    # 4. spinning ends with 590 kg
    login_as("supervisor")
    ended = client.post(f"/api/runs/{spin_id}/end", json={"output_kg": 590})
    assert ended.status_code == 200 and ended.json()["output_kg"] == 590.0
    o = order(code)
    assert o["progress"]["spun_kg"] == 590.0 and machine(spinner)["status"] == "idle"
    assert machine(spinner)["output_today"] == 590.0 and machine(spinner)["output_unit"] == "kg"

    # 5. weaving on that input; one roll, a shift change, two more rolls
    weave = client.post("/api/runs", json={"order_code": code, "machine_code": loom.code,
                                           "operator_worker_id": first.id, "input_run_id": spin_id})
    assert weave.status_code == 201, weave.text
    assert order(code)["stage"] == "weaving"
    r1 = client.post(f"/api/runs/{weave.json()['id']}/rolls", json={"metres": 1000})
    assert r1.status_code == 201 and r1.json()["status"] == "woven"
    handed = client.post(f"/api/runs/{weave.json()['id']}/handover", json={"operator_worker_id": second.id})
    assert handed.status_code == 201 and handed.json()["input_run_id"] == spin_id
    weave2 = handed.json()["id"]
    r2 = client.post(f"/api/runs/{weave2}/rolls", json={"metres": 800})
    r3 = client.post(f"/api/runs/{weave2}/rolls", json={"metres": 510})
    assert r2.status_code == 201 and r3.status_code == 201
    o = order(code)
    assert o["progress"]["woven_m"] == 2310.0 and o["stage"] == "weaving"
    assert machine(loom)["output_today"] == 2310.0 and machine(loom)["current_run"]["order_progress_pct"] == 46.2
    codes = [r1.json()["code"], r2.json()["code"], r3.json()["code"]]
    woven = client.get(f"/api/rolls?order_code={code}&status=woven").json()
    assert sorted(r["code"] for r in woven) == sorted(codes)
    runs = client.get(f"/api/runs?order_code={code}&stage=weaving").json()
    assert [r["id"] for r in runs] == [weave2, weave.json()["id"]] and runs[0]["metres"] == 1310.0

    # 6. dyeing: load the three rolls, end the run
    dye = client.post("/api/runs", json={"order_code": code, "machine_code": dyer.code,
                                         "operator_worker_id": first.id})
    assert dye.status_code == 201, dye.text
    dye_id = dye.json()["id"]
    loaded = client.post(f"/api/runs/{dye_id}/load-rolls", json={"roll_codes": codes})
    assert loaded.status_code == 200 and loaded.json()["metres"] == 2310.0
    assert order(code)["stage"] == "dyeing"
    assert {r["status"] for r in client.get(f"/api/rolls?order_code={code}").json()} == {"dyeing"}
    assert client.post(f"/api/runs/{dye_id}/end", json={}).status_code == 200

    # 7. dyed rolls wait for quality check; nothing is passed, rejected or dispatched yet
    o = order(code)
    assert o["stage"] == "quality_check" and o["progress"]["dyed_m"] == 2310.0
    assert (o["progress"]["passed_m"], o["progress"]["rejected_m"], o["progress"]["dispatched_m"]) == (0.0, 0.0, 0.0)
    assert {r["status"] for r in client.get(f"/api/rolls?order_code={code}").json()} == {"awaiting_qc"}
    assert machine(dyer)["output_today"] == 2310.0 and machine(dyer)["output_unit"] == "m"
    assert on_hand() == (212.5, 42.5)                                   # yarn is unchanged by the later stages
