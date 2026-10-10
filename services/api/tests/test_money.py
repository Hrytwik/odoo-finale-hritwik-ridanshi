"""B5 Task 4: payments (R13) and the receivables and payables lists. Hand-worked numbers: an invoice of 256,166.63; paying
100,000.00 leaves 156,166.63; 156,166.64 is one paisa too much; 156,166.63 brings the balance to 0.00. A bill of 800 kg at 250
= 200,000.00; paying 50,000 leaves 150,000.00."""
import datetime as dt
import threading
import time
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import today_ist
from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import BuyerPayment, Invoice, SupplierBill, SupplierPayment
from app.modules.money import schemas as ms
from app.modules.money import service
from tests.factories import make_buyer, make_dispatch, make_lot, make_supplier, make_yarn_type
from tests.helpers import wipe_database

ISSUED = dt.datetime(2026, 10, 1, 9, tzinfo=dt.UTC)
TOTAL = Decimal("256166.63")


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


@pytest.fixture
def acc(login_as):
    return login_as("accountant")


def make_invoice(db, buyer=None, total=TOTAL, issued=ISSUED, no=None) -> Invoice:
    buyer = buyer or make_buyer(db)
    dispatch = make_dispatch(db, buyer, state="dispatched", dispatched_at=issued)
    invoice = Invoice(invoice_no=no or f"INV-T{dispatch.id:04d}", dispatch_id=dispatch.id, buyer_id=buyer.id,
                      issued_at=issued, total_amount=total)
    db.add(invoice)
    db.flush()
    return invoice


def make_bill(db, qty=800, cost=250, due=dt.date(2026, 11, 9), bill_date=dt.date(2026, 10, 1)) -> SupplierBill:
    lot = make_lot(db, yarn_type=make_yarn_type(db), supplier=make_supplier(db), qty_kg=qty, cost_per_kg=cost)
    lot.bill.bill_date, lot.bill.due_date = bill_date, due
    db.flush()
    return lot.bill


def pay_buyer(client, invoice, amount, on=None, **over):
    return client.post("/api/payments/buyer", json={"invoice_no": invoice.invoice_no, "amount": amount,
                                                    "received_on": str(on or dt.date(2026, 10, 3)), **over})


def pay_supplier(client, bill, amount, on=None, **over):
    return client.post("/api/payments/supplier", json={"bill_id": bill.id, "amount": amount,
                                                       "paid_on": str(on or dt.date(2026, 10, 3)), **over})


def post_raw(client, path, raw):
    return client.post(path, content=raw, headers={"content-type": "application/json"})


def payment_count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# ---- buyer payments ----------------------------------------------------------------------------------

def test_the_worked_buyer_payments(client, db, acc, events):
    invoice = make_invoice(db)
    r = pay_buyer(client, invoice, 100000, reference="UTR-1")
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["invoice_no"] == invoice.invoice_no and row["total"] == 256166.63
    assert (row["paid"], row["balance"]) == (100000.0, 156166.63) and row["buyer"]["id"] == invoice.buyer_id
    assert events == [("payment.changed", invoice.id)]
    pay = db.scalar(select(BuyerPayment).where(BuyerPayment.invoice_id == invoice.id))
    assert pay.amount == Decimal("100000.00") and pay.received_at == dt.date(2026, 10, 3) and pay.reference == "UTR-1"
    events.clear()
    over = pay_buyer(client, invoice, 156166.64)
    assert over.status_code == 409 and over.json()["code"] == "OVERPAYMENT" and over.json()["field"] == "amount"
    assert "156166.63" in over.json()["message"] and events == [] and payment_count(db, BuyerPayment) == 1
    last = pay_buyer(client, invoice, 156166.63)
    assert last.status_code == 201 and last.json()["balance"] == 0.0 and last.json()["paid"] == 256166.63
    assert pay_buyer(client, invoice, 0.01).status_code == 409


@pytest.mark.parametrize("raw", ["0", "0.004", "-1", "NaN", "true", "1e9", '"abc"', "null"])
def test_bad_buyer_amounts_are_422_on_amount_and_store_nothing(client, db, acc, events, raw):
    invoice = make_invoice(db)
    body = '{"invoice_no": "%s", "amount": %s, "received_on": "2026-10-03"}' % (invoice.invoice_no, raw)
    r = post_raw(client, "/api/payments/buyer", body)
    assert r.status_code == 422 and "amount" in (r.json().get("fields") or {r.json()["field"]: ""})
    assert payment_count(db, BuyerPayment) == 0 and events == []


def test_buyer_payment_dates_and_reference(client, db, acc, events):
    invoice = make_invoice(db)
    tomorrow = today_ist() + dt.timedelta(days=1)
    r = pay_buyer(client, invoice, 10, on=tomorrow)
    assert r.status_code == 422 and r.json()["code"] == "FUTURE_DATE" and r.json()["field"] == "received_on"
    r = pay_buyer(client, invoice, 10, on=dt.date(2026, 9, 30))
    assert r.status_code == 422 and r.json()["field"] == "received_on"
    assert pay_buyer(client, invoice, 10, on=today_ist()).status_code == 201                    # today is fine
    assert pay_buyer(client, invoice, 10, on=dt.date(2026, 10, 1)).status_code == 201           # the invoice date is fine
    r = pay_buyer(client, invoice, 10, reference="R" * 121)
    assert r.status_code == 422 and r.json()["field"] == "reference"
    assert pay_buyer(client, invoice, 10, reference="R" * 120).status_code == 201
    assert payment_count(db, BuyerPayment) == 3


def test_an_unknown_invoice_is_404(client, db, acc):
    r = client.post("/api/payments/buyer", json={"invoice_no": "INV-9999999", "amount": 5, "received_on": "2026-10-03"})
    assert r.status_code == 404 and r.json()["field"] == "invoice_no"


# ---- supplier payments --------------------------------------------------------------------------------

def test_the_worked_supplier_payments_and_overdue(client, db, acc, events):
    bill = make_bill(db)
    r = pay_supplier(client, bill, 50000)
    assert r.status_code == 201, r.text
    row = r.json()
    assert (row["amount"], row["paid"], row["balance"], row["overdue"]) == (200000.0, 50000.0, 150000.0, False)
    assert row["bill_id"] == bill.id and row["lot_code"].startswith("L-") and row["due_date"] == "2026-11-09"
    assert events == [("payment.changed", bill.id)]
    events.clear()
    over = pay_supplier(client, bill, 150000.01)
    assert over.status_code == 409 and over.json()["code"] == "OVERPAYMENT" and "150000.00" in over.json()["message"]
    assert events == [] and payment_count(db, SupplierPayment) == 1
    done = pay_supplier(client, bill, 150000)
    assert done.status_code == 201 and done.json()["balance"] == 0.0 and done.json()["overdue"] is False
    assert pay_supplier(client, bill, 0.01).status_code == 409


def test_overdue_needs_a_past_due_date_and_something_still_owed(client, db, acc):
    late = make_bill(db, due=dt.date(2026, 10, 5))
    on_time = make_bill(db, due=today_ist() + dt.timedelta(days=5))
    rows = {r["bill_id"]: r for r in client.get("/api/money/payables").json()}
    assert rows[late.id]["overdue"] is True and rows[on_time.id]["overdue"] is False
    assert pay_supplier(client, late, 200000).json()["overdue"] is False                       # paid in full: no longer overdue


@pytest.mark.parametrize("raw", ["0", "0.004", "-1", "NaN", "true", "1e9", "null"])
def test_bad_supplier_amounts_are_422(client, db, acc, raw):
    bill = make_bill(db)
    r = post_raw(client, "/api/payments/supplier", '{"bill_id": %d, "amount": %s, "paid_on": "2026-10-03"}' % (bill.id, raw))
    assert r.status_code == 422 and payment_count(db, SupplierPayment) == 0


def test_supplier_payment_dates_reference_and_unknown_bill(client, db, acc):
    bill = make_bill(db)
    r = pay_supplier(client, bill, 10, on=today_ist() + dt.timedelta(days=1))
    assert r.status_code == 422 and r.json()["code"] == "FUTURE_DATE" and r.json()["field"] == "paid_on"
    r = pay_supplier(client, bill, 10, on=dt.date(2026, 9, 30))
    assert r.status_code == 422 and r.json()["field"] == "paid_on"
    assert pay_supplier(client, bill, 10, on=dt.date(2026, 10, 1)).status_code == 201           # the bill date is fine
    r = pay_supplier(client, bill, 10, reference="R" * 121)
    assert r.status_code == 422 and r.json()["field"] == "reference"
    r = client.post("/api/payments/supplier", json={"bill_id": 99999999, "amount": 5, "paid_on": "2026-10-03"})
    assert r.status_code == 404 and r.json()["field"] == "bill_id"


# ---- the lists -------------------------------------------------------------------------------------------

def test_receivables_include_paid_invoices_newest_first_and_match_the_invoice(client, db, acc):
    older = make_invoice(db, total=Decimal("1000.00"), issued=ISSUED)
    newer = make_invoice(db, total=Decimal("2000.00"), issued=ISSUED + dt.timedelta(days=2))
    assert pay_buyer(client, older, 1000).status_code == 201                                    # fully paid
    assert pay_buyer(client, newer, 500.5).status_code == 201
    rows = client.get("/api/money/receivables").json()
    assert [r["invoice_no"] for r in rows] == [newer.invoice_no, older.invoice_no]
    assert [(r["total"], r["paid"], r["balance"]) for r in rows] == [(2000.0, 500.5, 1499.5), (1000.0, 1000.0, 0.0)]
    assert rows[0]["buyer"]["id"] == newer.buyer_id and rows[0]["issued_at"]
    inv = client.get(f"/api/invoices/{newer.invoice_no}").json()
    assert (inv["total_amount"], inv["paid_amount"], inv["balance"]) == (2000.0, 500.5, 1499.5)


def test_payables_are_soonest_due_first_and_show_the_lot(client, db, acc):
    later = make_bill(db, due=dt.date(2026, 12, 1))
    sooner = make_bill(db, due=dt.date(2026, 10, 20), qty=100, cost=10)
    rows = client.get("/api/money/payables").json()
    assert [r["bill_id"] for r in rows] == [sooner.id, later.id]
    assert rows[0]["amount"] == 1000.0 and rows[0]["lot_code"] == sooner.lot.lot_code and rows[0]["supplier"]["id"] == sooner.supplier_id
    assert rows[0]["bill_no"] == sooner.bill_no and rows[0]["bill_date"] == "2026-10-01"


def test_receiving_a_lot_creates_a_payable_through_the_api(client, db, login_as):
    login_as("store")
    yt, sup = make_yarn_type(db), make_supplier(db)
    lot = client.post("/api/lots", json={"yarn_type_id": yt.id, "supplier_id": sup.id, "qty_kg": 800, "cost_per_kg": 250,
                                         "challan_no": "CH-PAY"}).json()
    login_as("accountant")
    [row] = [r for r in client.get("/api/money/payables").json() if r["lot_code"] == lot["lot_code"]]
    assert (row["bill_no"], row["amount"], row["paid"], row["balance"]) == ("CH-PAY", 200000.0, 0.0, 200000.0)


def test_empty_lists(client, db, acc):
    assert client.get("/api/money/receivables").json() == [] and client.get("/api/money/payables").json() == []


@pytest.mark.parametrize("role, ok", [("accountant", True), ("owner", True), ("store", False), ("supervisor", False),
                                      ("qc", False), ("dispatch", False), ("buyer", False)])
def test_who_can_use_money(client, db, login_as, role, ok):
    login_as(role)
    invoice, bill = make_invoice(db), make_bill(db)
    assert (client.get("/api/money/receivables").status_code == 200) is ok
    assert (client.get("/api/money/payables").status_code == 200) is ok
    assert (pay_buyer(client, invoice, 1).status_code == 201) is ok
    assert (pay_supplier(client, bill, 1).status_code == 201) is ok


# ---- two payments at once ----------------------------------------------------------------------------------

def committed_invoice(engine, total="100.00"):
    with Session(engine) as setup:
        invoice = make_invoice(setup, total=Decimal(total))
        setup.commit()
        return invoice.invoice_no, invoice.id


def committed_bill(engine):
    with Session(engine) as setup:
        bill = make_bill(setup, qty=1, cost=100)
        setup.commit()
        return bill.id


def test_two_buyer_payments_that_together_exceed_the_balance_one_wins(engine):
    try:
        for _ in range(5):
            number, invoice_id = committed_invoice(engine)
            barrier = threading.Barrier(2)
            results: list[str] = []

            def go(number=number, results=results, barrier=barrier):
                with Session(engine) as session:
                    barrier.wait()
                    try:
                        service.record_buyer_payment(session, ms.BuyerPaymentIn(
                            invoice_no=number, amount=60, received_on=dt.date(2026, 10, 3)))
                        results.append("ok")
                    except AppError as exc:
                        results.append(exc.code)

            threads = [threading.Thread(target=go) for _ in range(2)]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert sorted(results) == ["OVERPAYMENT", "ok"], results
            with Session(engine) as check:
                assert check.scalar(select(func.sum(BuyerPayment.amount)).where(BuyerPayment.invoice_id == invoice_id)) == Decimal("60.00")
            wipe_database(engine)
    finally:
        wipe_database(engine)


def test_two_supplier_payments_that_together_exceed_the_balance_one_wins(engine):
    try:
        for _ in range(5):
            bill_id = committed_bill(engine)
            barrier = threading.Barrier(2)
            results: list[str] = []

            def go(bill_id=bill_id, results=results, barrier=barrier):
                with Session(engine) as session:
                    barrier.wait()
                    try:
                        service.record_supplier_payment(session, ms.SupplierPaymentIn(
                            bill_id=bill_id, amount=60, paid_on=dt.date(2026, 10, 3)))
                        results.append("ok")
                    except AppError as exc:
                        results.append(exc.code)

            threads = [threading.Thread(target=go) for _ in range(2)]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert sorted(results) == ["OVERPAYMENT", "ok"], results
            wipe_database(engine)
    finally:
        wipe_database(engine)


def _held(engine, model, make, pay):
    """A session holds the row lock and records its own payment of 60 by hand; the waiting payment of 60 must then be refused."""
    ident = make(engine)
    outcome: list[str] = []

    def waiter():
        with Session(engine) as session:
            try:
                pay(session, ident)
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            row = holder.scalar(select(model).where(model.id == ident[1]).with_for_update())
            thread = threading.Thread(target=waiter)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "the second payment must be waiting on the row lock"
            if model is Invoice:
                holder.add(BuyerPayment(invoice_id=row.id, amount=Decimal("60.00"), received_at=dt.date(2026, 10, 3)))
            else:
                holder.add(SupplierPayment(bill_id=row.id, amount=Decimal("60.00"), paid_at=dt.date(2026, 10, 3)))
            holder.commit()
            thread.join(timeout=10)
        return outcome
    finally:
        wipe_database(engine)


def test_a_buyer_payment_waits_for_the_invoice_lock(engine):
    out = _held(engine, Invoice, committed_invoice, lambda s, ident: service.record_buyer_payment(
        s, ms.BuyerPaymentIn(invoice_no=ident[0], amount=60, received_on=dt.date(2026, 10, 3))))
    assert out == ["OVERPAYMENT"]


def test_a_supplier_payment_waits_for_the_bill_lock(engine):
    out = _held(engine, SupplierBill, lambda e: (None, committed_bill(e)), lambda s, ident: service.record_supplier_payment(
        s, ms.SupplierPaymentIn(bill_id=ident[1], amount=60, paid_on=dt.date(2026, 10, 3))))
    assert out == ["OVERPAYMENT"]
