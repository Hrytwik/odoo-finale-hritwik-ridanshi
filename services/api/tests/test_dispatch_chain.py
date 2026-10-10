"""B5 Task 5: the whole chain through the API, B2 to B5 together. A 1,000 m order (rolls of 600 m and 400 m at 120): spin,
weave, dye, QC (roll B is sent back, mended and passes), then a truck: roll B is refused while it still waits for rework,
both rolls load once passed, the dispatch is confirmed into an invoice of 120,000.00, the buyer reads it, 70,000 is paid
(balance 50,000.00), an overpayment is refused, and the supplier bill for the yarn lot shows in payables."""
import datetime as dt

from app.core.auth import COOKIE_NAME, create_token
from tests.factories import (
    make_fabric_type, make_machine, make_supplier, make_user, make_worker, make_yarn_type,
)


def test_receive_to_paid_invoice_through_the_api(client, db, login_as):
    cotton = make_yarn_type(db, reorder_level_kg=10)
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.12, wastage_pct=5)
    supplier = make_supplier(db)
    spinner, loom, dyer = (make_machine(db, stage=s) for s in ("spinning", "weaving", "dyeing"))
    operator = make_worker(db)
    buyer_user = login_as("buyer")
    mine = buyer_user.buyer
    owner_user = make_user(db, role="owner")

    def as_owner(path):
        before = client.cookies.get(COOKIE_NAME)
        client.cookies.set(COOKIE_NAME, create_token(owner_user.id))
        out = client.get(path).json()
        client.cookies.set(COOKIE_NAME, before)
        return out

    def statuses(code):
        return {r["code"]: r["status"] for r in as_owner(f"/api/rolls?order_code={code}")}

    # yarn in, order confirmed
    login_as("store")
    lot = client.post("/api/lots", json={"yarn_type_id": cotton.id, "supplier_id": supplier.id, "qty_kg": 200,
                                         "cost_per_kg": 250, "challan_no": "CH-CASH"}).json()
    login_as("owner")
    code = client.post("/api/orders", json={"buyer_id": mine.id, "fabric_type_id": fabric.id, "colour": "navy",
                                            "qty_metres": 1000, "price_per_metre": 120,
                                            "deadline": str(dt.date.today() + dt.timedelta(days=30))}).json()["code"]
    client.post(f"/api/orders/{code}/confirm")

    # spin, weave, dye
    login_as("supervisor")
    spin = client.post("/api/runs", json={"order_code": code, "machine_code": spinner.code,
                                          "operator_worker_id": operator.id}).json()
    login_as("store")
    client.post("/api/movements/issue", json={"lot_code": lot["lot_code"], "run_id": spin["id"], "qty_kg": 120})
    login_as("supervisor")
    client.post(f"/api/runs/{spin['id']}/end", json={"output_kg": 118})
    weave = client.post("/api/runs", json={"order_code": code, "machine_code": loom.code,
                                           "operator_worker_id": operator.id, "input_run_id": spin["id"]}).json()
    roll_a = client.post(f"/api/runs/{weave['id']}/rolls", json={"metres": 600}).json()["code"]
    roll_b = client.post(f"/api/runs/{weave['id']}/rolls", json={"metres": 400}).json()["code"]
    dye = client.post("/api/runs", json={"order_code": code, "machine_code": dyer.code,
                                         "operator_worker_id": operator.id}).json()
    client.post(f"/api/runs/{dye['id']}/load-rolls", json={"roll_codes": [roll_a, roll_b]})
    client.post(f"/api/runs/{dye['id']}/end", json={})

    # QC: A passes, B is sent back
    login_as("qc")
    assert client.post("/api/qc/inspections", json={"roll_code": roll_a, "verdict": "pass", "defects": []}).status_code == 201
    assert client.post("/api/qc/inspections", json={"roll_code": roll_b, "verdict": "rework",
                                                    "defects": [{"defect_type": "hole", "count": 2}]}).status_code == 201

    # a truck is created while roll B still waits for rework
    login_as("dispatch")
    truck = client.post("/api/dispatches", json={"buyer_id": mine.id, "vehicle_no": "KA01AB1234", "driver_name": "Imran"})
    assert truck.status_code == 201, truck.text
    truck_code = truck.json()["code"]
    assert client.post(f"/api/dispatches/{truck_code}/items", json={"roll_code": roll_a}).status_code == 200
    refused = client.post(f"/api/dispatches/{truck_code}/items", json={"roll_code": roll_b})
    assert refused.status_code == 409 and refused.json()["code"] == "ROLL_NOT_PASSED" and "awaiting_rework" in refused.json()["message"]
    again = client.post(f"/api/dispatches/{truck_code}/items", json={"roll_code": roll_a})
    assert again.status_code == 409 and again.json()["code"] == "ALREADY_DISPATCHED"
    assert statuses(code)[roll_a] == "loading"

    # B is mended and passes, then it loads
    login_as("supervisor")
    mend = client.post("/api/rework-runs", json={"roll_code": roll_b, "operator_worker_id": operator.id}).json()
    client.post(f"/api/runs/{mend['id']}/end", json={})
    login_as("qc")
    assert client.post("/api/qc/inspections", json={"roll_code": roll_b, "verdict": "pass", "defects": []}).status_code == 201
    login_as("dispatch")
    loaded = client.post(f"/api/dispatches/{truck_code}/items", json={"roll_code": roll_b})
    assert loaded.status_code == 200 and loaded.json()["total_metres"] == 1000.0
    [row] = loaded.json()["orders"]
    assert (row["ordered_m"], row["loaded_m"], row["remaining_m"], row["over_shipped"]) == (1000.0, 1000.0, 0.0, False)

    # confirm: the invoice
    done = client.post(f"/api/dispatches/{truck_code}/confirm")
    assert done.status_code == 200 and done.json()["state"] == "dispatched"
    number = done.json()["invoice_no"]
    assert client.post(f"/api/dispatches/{truck_code}/confirm").json()["code"] == "DISPATCH_LOCKED"
    assert {r["status"] for r in done.json()["rolls"]} == {"dispatched"}
    o = as_owner(f"/api/orders/{code}")
    assert o["progress"]["dispatched_m"] == 1000.0 and o["stage"] == "dispatched"
    p = as_owner(f"/api/rolls/{roll_b}/passport")
    assert p["roll"]["status"] == "dispatched" and p["dispatch"]["code"] == truck_code and p["dispatch"]["invoice_no"] == number

    # the order's own buyer reads the invoice
    client.cookies.set(COOKIE_NAME, create_token(buyer_user.id))
    inv = client.get(f"/api/invoices/{number}").json()
    assert inv["total_amount"] == 120000.0 and inv["paid_amount"] == 0.0 and inv["balance"] == 120000.0
    [line] = inv["lines"]
    assert (line["order_code"], line["metres"], line["rate"], line["amount"]) == (code, 1000.0, 120.0, 120000.0)
    assert sorted(line["roll_codes"]) == sorted([roll_a, roll_b])

    # money: receivables and payables
    login_as("accountant")
    [rec] = [r for r in client.get("/api/money/receivables").json() if r["invoice_no"] == number]
    assert (rec["total"], rec["paid"], rec["balance"]) == (120000.0, 0.0, 120000.0)
    paid = client.post("/api/payments/buyer", json={"invoice_no": number, "amount": 70000, "received_on": str(dt.date.today())})
    assert paid.status_code == 201 and (paid.json()["paid"], paid.json()["balance"]) == (70000.0, 50000.0)
    over = client.post("/api/payments/buyer", json={"invoice_no": number, "amount": 50000.01, "received_on": str(dt.date.today())})
    assert over.status_code == 409 and over.json()["code"] == "OVERPAYMENT" and "50000.00" in over.json()["message"]
    [bill] = [b for b in client.get("/api/money/payables").json() if b["lot_code"] == lot["lot_code"]]
    assert (bill["bill_no"], bill["amount"], bill["balance"], bill["overdue"]) == ("CH-CASH", 50000.0, 50000.0, False)
    settled = client.post("/api/payments/supplier", json={"bill_id": bill["bill_id"], "amount": 20000, "paid_on": str(dt.date.today())})
    assert settled.status_code == 201 and settled.json()["balance"] == 30000.0

    # the invoice now shows what was paid
    login_as("owner")
    inv = client.get(f"/api/invoices/{number}").json()
    assert (inv["paid_amount"], inv["balance"]) == (70000.0, 50000.0)
    assert client.get("/api/dispatches?state=dispatched").json()[0]["code"] == truck_code
