import datetime as dt

from pydantic import BaseModel

from app.core.schemas import Money, NonBlank, Out, Ref


class ReceivableRow(Out):
    invoice_no: str
    buyer: Ref
    issued_at: dt.datetime
    total: float
    paid: float
    balance: float


class PayableRow(Out):
    bill_id: int
    bill_no: str
    supplier: Ref
    lot_code: str
    bill_date: dt.date
    due_date: dt.date
    amount: float
    paid: float
    balance: float
    overdue: bool


class BuyerPaymentIn(BaseModel):
    invoice_no: NonBlank
    amount: Money
    received_on: dt.date
    reference: NonBlank | None = None


class SupplierPaymentIn(BaseModel):
    bill_id: int
    amount: Money
    paid_on: dt.date
    reference: NonBlank | None = None
