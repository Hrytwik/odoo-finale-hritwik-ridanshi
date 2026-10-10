import datetime as dt

import pytest

from app.core.errors import map_integrity_error
from app.db.models import (
    BuyerPayment, DispatchItem, Invoice, InvoiceLine, LlmEvalRun, LlmSettings, SupplierBill, SupplierPayment,
    YarnMovement,
)
from tests.factories import (
    make_buyer, make_dispatch, make_lot, make_machine, make_order, make_roll, make_run, make_user,
)
from tests.helpers import violates

NOW = dt.datetime(2026, 10, 10, 12, tzinfo=dt.UTC)


def _spin_run(db):
    return make_run(db, make_order(db), make_machine(db, stage="spinning"))


# ---- yarn lots and the ledger -------------------------------------------------------------

def test_receiving_creates_ledger_row_and_bill(db):
    lot = make_lot(db, qty_kg=800, cost_per_kg=250)
    assert lot.movements[0].kind == "receipt" and float(lot.movements[0].qty_kg) == 800
    assert float(lot.bill.amount) == 200000


def test_same_challan_twice_maps_to_duplicate_challan(db):
    lot = make_lot(db)
    with violates("uq_yarn_lots_supplier_id_challan_no_yarn_type_id") as _:
        make_lot(db, yarn_type=lot.yarn_type, supplier=lot.supplier, challan_no=lot.challan_no)


def test_the_duplicate_challan_error_reaches_the_user_as_a_clear_message(db):
    from sqlalchemy.exc import IntegrityError

    lot = make_lot(db)
    with pytest.raises(IntegrityError) as exc:
        make_lot(db, yarn_type=lot.yarn_type, supplier=lot.supplier, challan_no=lot.challan_no)
    err = map_integrity_error(exc.value)
    assert (err.code, err.field, err.status) == ("DUPLICATE_CHALLAN", "challan_no", 409)


def test_same_challan_number_is_fine_for_another_supplier(db):
    lot = make_lot(db)
    assert make_lot(db, yarn_type=lot.yarn_type, challan_no=lot.challan_no).id


@pytest.mark.parametrize("kw,constraint", [
    ({"cost_per_kg": 0}, "ck_yarn_lots_cost_pos"),
    ({"challan_no": "  "}, "ck_yarn_lots_challan_no_nonblank"),
    ({"is_blocked": True}, "ck_yarn_lots_blocked_has_time"),
])
def test_lot_rules(db, kw, constraint):
    with violates(constraint):
        make_lot(db, **kw)


@pytest.mark.parametrize("kind,qty,needs_run,constraint", [
    ("receipt", -5, False, "ck_yarn_movements_sign_matches_kind"),
    ("issue", 5, True, "ck_yarn_movements_sign_matches_kind"),
    ("return", -5, True, "ck_yarn_movements_sign_matches_kind"),
    ("issue", -5, False, "ck_yarn_movements_run_link"),
    ("receipt", 5, True, "ck_yarn_movements_run_link"),
    ("receipt", 0, False, "ck_yarn_movements_qty_nonzero"),
    ("scrap", 5, False, "ck_yarn_movements_kind_valid"),
])
def test_movement_rules(db, kind, qty, needs_run, constraint):
    lot = make_lot(db)
    run_id = _spin_run(db).id if needs_run else None
    with violates(constraint):
        db.add(YarnMovement(yarn_lot_id=lot.id, kind=kind, qty_kg=qty, production_run_id=run_id,
                            moved_by=make_user(db).id))
        db.flush()


def test_issue_with_a_run_is_valid(db):
    lot = make_lot(db)
    db.add(YarnMovement(yarn_lot_id=lot.id, kind="issue", qty_kg=-50, production_run_id=_spin_run(db).id,
                        moved_by=make_user(db).id))
    db.flush()


@pytest.mark.parametrize("qty", [-3, 3])
def test_adjustment_may_go_either_way_but_needs_a_note(db, qty):
    lot = make_lot(db)
    db.add(YarnMovement(yarn_lot_id=lot.id, kind="adjustment", qty_kg=qty, note="stock count",
                        moved_by=make_user(db).id))
    db.flush()
    with violates("ck_yarn_movements_adjust_note"):
        db.add(YarnMovement(yarn_lot_id=lot.id, kind="adjustment", qty_kg=qty, note="  ",
                            moved_by=make_user(db).id))
        db.flush()


# ---- dispatch, invoices, payments ---------------------------------------------------------

def test_roll_can_be_on_only_one_dispatch(db):
    buyer = make_buyer(db)
    order = make_order(db, buyer=buyer)
    roll = make_roll(db, order, make_run(db, order, make_machine(db, stage="weaving")))
    d1, d2 = make_dispatch(db, buyer), make_dispatch(db, buyer)
    db.add(DispatchItem(dispatch_id=d1.id, roll_id=roll.id))
    db.flush()
    with violates("uq_dispatch_items_roll_id"):
        db.add(DispatchItem(dispatch_id=d2.id, roll_id=roll.id))
        db.flush()


def test_the_double_dispatch_error_reaches_the_user_as_a_clear_message(db):
    from sqlalchemy.exc import IntegrityError

    buyer = make_buyer(db)
    order = make_order(db, buyer=buyer)
    roll = make_roll(db, order, make_run(db, order, make_machine(db, stage="weaving")))
    d1, d2 = make_dispatch(db, buyer), make_dispatch(db, buyer)
    db.add(DispatchItem(dispatch_id=d1.id, roll_id=roll.id))
    db.flush()
    with pytest.raises(IntegrityError) as exc:
        db.add(DispatchItem(dispatch_id=d2.id, roll_id=roll.id))
        db.flush()
    assert map_integrity_error(exc.value).code == "ALREADY_DISPATCHED"


@pytest.mark.parametrize("kw,constraint", [
    ({"state": "dispatched", "dispatched_at": None}, "ck_dispatches_dispatched_has_time"),
    ({"state": "loading", "dispatched_at": NOW}, "ck_dispatches_dispatched_has_time"),
    ({"state": "sent"}, "ck_dispatches_state_valid"),
    ({"vehicle_no": "  "}, "ck_dispatches_vehicle_no_nonblank"),
])
def test_dispatch_rules(db, kw, constraint):
    with violates(constraint):
        make_dispatch(db, make_buyer(db), **kw)


def _invoice(db):
    buyer = make_buyer(db)
    d = make_dispatch(db, buyer, state="dispatched", dispatched_at=NOW)
    inv = Invoice(invoice_no=f"INV-{d.id}", dispatch_id=d.id, buyer_id=buyer.id, issued_at=NOW, total_amount=1000)
    db.add(inv)
    db.flush()
    return inv, make_order(db, buyer=buyer)


def test_one_invoice_per_dispatch(db):
    inv, _ = _invoice(db)
    with violates("uq_invoices_dispatch_id"):
        db.add(Invoice(invoice_no="INV-X", dispatch_id=inv.dispatch_id, buyer_id=inv.buyer_id, issued_at=NOW,
                       total_amount=1))
        db.flush()


@pytest.mark.parametrize("kw,constraint", [
    ({"metres": 0}, "ck_invoice_lines_metres_pos"),
    ({"rate": 0}, "ck_invoice_lines_rate_pos"),
    ({"amount": -1}, "ck_invoice_lines_amount_nonneg"),
])
def test_invoice_line_rules(db, kw, constraint):
    inv, order = _invoice(db)
    with violates(constraint):
        db.add(InvoiceLine(**{"invoice_id": inv.id, "order_id": order.id, "metres": 10, "rate": 100,
                              "amount": 1000, **kw}))
        db.flush()


def test_payments_must_be_positive(db):
    inv, _ = _invoice(db)
    with violates("ck_buyer_payments_amount_pos"):
        db.add(BuyerPayment(invoice_id=inv.id, amount=0, received_at=NOW.date()))
        db.flush()


def test_a_bill_is_one_per_lot_and_payments_must_be_positive(db):
    lot = make_lot(db)
    with violates("uq_supplier_bills_yarn_lot_id"):
        db.add(SupplierBill(supplier_id=lot.supplier_id, yarn_lot_id=lot.id, bill_no="X", amount=1,
                            bill_date=NOW.date(), due_date=NOW.date()))
        db.flush()


def test_bill_cannot_fall_due_before_it_is_issued(db):
    lot = make_lot(db)
    lot.bill.due_date = lot.bill.bill_date - dt.timedelta(days=1)
    with violates("ck_supplier_bills_due_after_bill"):
        db.flush()


def test_supplier_payment_must_be_positive(db):
    lot = make_lot(db)
    with violates("ck_supplier_payments_amount_pos"):
        db.add(SupplierPayment(bill_id=lot.bill.id, amount=-5, paid_at=NOW.date()))
        db.flush()


# ---- language-model settings --------------------------------------------------------------

def test_llm_settings_is_a_single_row(db):
    db.add(LlmSettings(id=1, provider="anthropic", model="claude-opus-5-5"))
    db.flush()
    with violates("ck_llm_settings_single_row"):
        db.add(LlmSettings(id=2, provider="anthropic", model="x"))
        db.flush()


@pytest.mark.parametrize("kw,constraint", [
    ({"provider": "openai_compatible"}, "ck_llm_settings_base_url_needed"),
    ({"provider": "gemini"}, "ck_llm_settings_provider_valid"),
    ({"model": "  "}, "ck_llm_settings_model_nonblank"),
])
def test_llm_settings_rules(db, kw, constraint):
    with violates(constraint):
        db.add(LlmSettings(**{"id": 1, "provider": "anthropic", "model": "m", **kw}))
        db.flush()


def test_openai_compatible_with_a_server_address_is_valid(db):
    db.add(LlmSettings(id=1, provider="openai_compatible", model="llama3.1", base_url="http://localhost:11434/v1"))
    db.flush()


@pytest.mark.parametrize("score,total", [(5, 0), (-1, 15), (16, 15)])
def test_report_card_score_must_fit_within_the_total(db, score, total):
    with violates("ck_llm_eval_runs_score_range"):
        db.add(LlmEvalRun(provider="anthropic", model="m", score=score, total=total, details=[]))
        db.flush()


def test_report_card_run_saves(db):
    db.add(LlmEvalRun(provider="anthropic", model="m", score=11, total=15, details=[{"q": "x", "pass": True}]))
    db.flush()
