import datetime as dt

from app.core.schemas import Ref
from app.modules.dispatch.schemas import DispatchOut, InvoiceLineOut, InvoiceOut, OrderLoadSummary
from app.modules.floor.examples import NOW, ROLL

SHARMA = Ref(id=1, name="Sharma Fabrics")
ROLLS = [ROLL.model_copy(update={"id": 131 + i, "code": f"R-013{1 + i}", "status": "dispatched"}) for i in range(3)]
DISPATCH = DispatchOut(
    id=7, code="DSP-0007", buyer=SHARMA, vehicle_no="KA01AB1234", driver_name="Manju", state="dispatched",
    created_at=NOW - dt.timedelta(days=1, hours=2), dispatched_at=NOW - dt.timedelta(days=1), rolls=ROLLS,
    orders=[OrderLoadSummary(order_code="ORD-0012", ordered_m=5000, previously_dispatched_m=0, loaded_m=330,
                             remaining_m=4670, over_shipped=False)],
    total_metres=330, invoice_no="INV-0007", warnings=[],
)
LOADING = DISPATCH.model_copy(update={"id": 8, "code": "DSP-0008", "state": "loading", "dispatched_at": None,
                                      "invoice_no": None, "created_at": NOW})
INVOICE = InvoiceOut(
    invoice_no="INV-0007", issued_at=NOW - dt.timedelta(days=1), buyer=SHARMA, dispatch_code="DSP-0007",
    vehicle_no="KA01AB1234",
    lines=[InvoiceLineOut(order_code="ORD-0012", fabric="Poplin 58in", colour="navy", metres=330, rate=120,
                          amount=39600, roll_codes=[r.code for r in ROLLS])],
    total_amount=39600, paid_amount=20000, balance=19600,
)
