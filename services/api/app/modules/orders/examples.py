import datetime as dt

from app.core.schemas import Ref
from app.modules.orders.schemas import OrderOut, Progress, YarnCheckLine, YarnCheckOut
from app.modules.store.examples import COTTON

ORDER = OrderOut(
    id=12, code="ORD-0012", buyer=Ref(id=1, name="Sharma Fabrics"), fabric_type=Ref(id=1, name="Poplin 58in"),
    colour="navy", qty_metres=5000, price_per_metre=120, deadline=dt.date(2026, 10, 20), state="confirmed",
    stage="weaving", created_at=dt.datetime(2026, 10, 1, 10, tzinfo=dt.UTC),
    confirmed_at=dt.datetime(2026, 10, 1, 11, tzinfo=dt.UTC),
    progress=Progress(need_kg=630, spun_kg=587.5, woven_m=2310, dyed_m=1540, passed_m=1210, rejected_m=110,
                      dispatched_m=330),
    yarn_status="short", short_kg=230, delivery_date=dt.date(2026, 10, 22), days_late=2,
)
DRAFT = ORDER.model_copy(update={
    "id": 15, "code": "ORD-0015", "state": "draft", "stage": "draft", "confirmed_at": None,
    "progress": Progress(need_kg=630, spun_kg=0, woven_m=0, dyed_m=0, passed_m=0, rejected_m=0, dispatched_m=0),
    "delivery_date": None, "days_late": None,
})
YARN_CHECK = YarnCheckOut(order_code="ORD-0012", can_start=False, lines=[
    YarnCheckLine(yarn_type=COTTON, need_kg=630, issued_kg=0, outstanding_kg=630, available_kg=400, short_kg=230),
])
