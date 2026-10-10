import datetime as dt

from app.core.schemas import Ref
from app.modules.dispatch.examples import INVOICE
from app.modules.money.schemas import PayableRow, ReceivableRow

RECEIVABLE = ReceivableRow(invoice_no=INVOICE.invoice_no, buyer=INVOICE.buyer, issued_at=INVOICE.issued_at,
                           total=39600, paid=20000, balance=19600)
PAYABLE = PayableRow(bill_id=17, bill_no="CH-5521", supplier=Ref(id=1, name="Vardhman Yarns"), lot_code="L-0017",
                     bill_date=dt.date(2026, 10, 10), due_date=dt.date(2026, 11, 9), amount=200000, paid=0,
                     balance=200000, overdue=False)
