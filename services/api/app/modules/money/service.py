"""Money: what buyers owe us (receivables), what we owe suppliers (payables), and the payments against them (R13).
`paid` and `balance` are always summed from the payment tables, never stored. A payment locks the invoice or bill row first,
so two payments at the same moment cannot both fit under the limit."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.clock import IST, today_ist
from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.core.money import q_money, to_float
from app.core.schemas import Ref
from app.core.validate import exact_positive, invalid, not_found
from app.db.models import Buyer, BuyerPayment, Invoice, Supplier, SupplierBill, SupplierPayment, YarnLot
from app.modules.money import schemas as s

REFERENCE_MAX = 120      # the column size; checked here so the answer is a 422 on the field

_RECEIVABLES_SQL = text("""
SELECT i.id, i.invoice_no, i.buyer_id, i.issued_at, i.total_amount,
       COALESCE((SELECT SUM(p.amount) FROM buyer_payments p WHERE p.invoice_id = i.id), 0) AS paid
FROM invoices i ORDER BY i.issued_at DESC, i.id DESC
""")
_PAYABLES_SQL = text("""
SELECT b.id, b.bill_no, b.supplier_id, l.lot_code, b.bill_date, b.due_date, b.amount,
       COALESCE((SELECT SUM(p.amount) FROM supplier_payments p WHERE p.bill_id = b.id), 0) AS paid
FROM supplier_bills b JOIN yarn_lots l ON l.id = b.yarn_lot_id ORDER BY b.due_date, b.id
""")


def _receivable(buyer: Buyer, row) -> s.ReceivableRow:
    return s.ReceivableRow(invoice_no=row["invoice_no"], buyer=Ref(id=buyer.id, name=buyer.name),
                           issued_at=row["issued_at"], total=to_float(row["total_amount"]), paid=to_float(row["paid"]),
                           balance=to_float(row["total_amount"] - row["paid"]))


def _payable(supplier: Supplier, row, today: dt.date) -> s.PayableRow:
    balance = row["amount"] - row["paid"]
    return s.PayableRow(bill_id=row["id"], bill_no=row["bill_no"], supplier=Ref(id=supplier.id, name=supplier.name),
                        lot_code=row["lot_code"], bill_date=row["bill_date"], due_date=row["due_date"],
                        amount=to_float(row["amount"]), paid=to_float(row["paid"]), balance=to_float(balance),
                        overdue=row["due_date"] < today and balance > 0)


def receivables(db: Session) -> list[s.ReceivableRow]:
    rows = list(db.execute(_RECEIVABLES_SQL).mappings())
    buyers = {b.id: b for b in db.scalars(select(Buyer))}
    return [_receivable(buyers[r["buyer_id"]], r) for r in rows]


def payables(db: Session) -> list[s.PayableRow]:
    rows = list(db.execute(_PAYABLES_SQL).mappings())
    suppliers = {sp.id: sp for sp in db.scalars(select(Supplier))}
    today = today_ist()
    return [_payable(suppliers[r["supplier_id"]], r, today) for r in rows]


def _check_payment_date(on: dt.date, earliest: dt.date, field: str, what: str) -> None:
    if on > today_ist():
        raise AppError("FUTURE_DATE", "A payment cannot be dated in the future", field=field, status=422)
    if on < earliest:
        raise invalid(f"A payment cannot be dated before the {what} ({earliest.isoformat()})", field)


def _check_reference(reference: str | None) -> None:
    if reference is not None and len(reference) > REFERENCE_MAX:
        raise invalid(f"The reference is too long (at most {REFERENCE_MAX} characters)", "reference")


def _overpayment(owed: Decimal, what: str) -> AppError:
    return AppError("OVERPAYMENT", f"Only ₹{owed:.2f} is still owed on this {what}", field="amount")


def record_buyer_payment(db: Session, body: s.BuyerPaymentIn) -> s.ReceivableRow:
    invoice = db.scalar(select(Invoice).where(Invoice.invoice_no == body.invoice_no))
    if invoice is None:
        raise not_found("Invoice", "invoice_no")
    invoice = db.scalar(select(Invoice).where(Invoice.id == invoice.id).with_for_update()
                        .execution_options(populate_existing=True))
    amount = exact_positive(body.amount, "amount", q_money)
    _check_reference(body.reference)
    _check_payment_date(body.received_on, invoice.issued_at.astimezone(IST).date(), "received_on", "invoice date")
    paid = db.scalar(select(func.coalesce(func.sum(BuyerPayment.amount), 0)).where(BuyerPayment.invoice_id == invoice.id))
    if paid + amount > invoice.total_amount:
        raise _overpayment(invoice.total_amount - paid, "invoice")
    db.add(BuyerPayment(invoice_id=invoice.id, amount=amount, received_at=body.received_on, reference=body.reference))
    commit(db)
    broadcaster.publish("payment.changed", invoice.id)
    row = db.execute(text("""SELECT i.id, i.invoice_no, i.buyer_id, i.issued_at, i.total_amount,
        COALESCE((SELECT SUM(p.amount) FROM buyer_payments p WHERE p.invoice_id = i.id), 0) AS paid
        FROM invoices i WHERE i.id = :id"""), {"id": invoice.id}).mappings().one()
    return _receivable(db.get(Buyer, invoice.buyer_id), row)


def record_supplier_payment(db: Session, body: s.SupplierPaymentIn) -> s.PayableRow:
    bill = db.get(SupplierBill, body.bill_id)
    if bill is None:
        raise not_found("Supplier bill", "bill_id")
    bill = db.scalar(select(SupplierBill).where(SupplierBill.id == bill.id).with_for_update()
                     .execution_options(populate_existing=True))
    amount = exact_positive(body.amount, "amount", q_money)
    _check_reference(body.reference)
    _check_payment_date(body.paid_on, bill.bill_date, "paid_on", "bill date")
    paid = db.scalar(select(func.coalesce(func.sum(SupplierPayment.amount), 0)).where(SupplierPayment.bill_id == bill.id))
    if paid + amount > bill.amount:
        raise _overpayment(bill.amount - paid, "bill")
    db.add(SupplierPayment(bill_id=bill.id, amount=amount, paid_at=body.paid_on, reference=body.reference))
    commit(db)
    broadcaster.publish("payment.changed", bill.id)
    row = db.execute(text("""SELECT b.id, b.bill_no, b.supplier_id, l.lot_code, b.bill_date, b.due_date, b.amount,
        COALESCE((SELECT SUM(p.amount) FROM supplier_payments p WHERE p.bill_id = b.id), 0) AS paid
        FROM supplier_bills b JOIN yarn_lots l ON l.id = b.yarn_lot_id WHERE b.id = :id"""), {"id": bill.id}).mappings().one()
    return _payable(db.get(Supplier, bill.supplier_id), row, today_ist())
