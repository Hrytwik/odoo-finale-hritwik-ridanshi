import datetime as dt

from app.core.enums import OrderStage
from app.core.schemas import Out


class PortalOrder(Out):
    code: str
    fabric: str
    colour: str
    qty_metres: float
    stage: OrderStage
    progress_pct: float
    deadline: dt.date
    delivery_date: dt.date | None


class TimelineEvent(Out):
    at: dt.datetime
    label: str


class PortalDispatch(Out):
    code: str
    dispatched_at: dt.datetime
    metres: float
    invoice_no: str | None


class PortalOrderDetail(PortalOrder):
    timeline: list[TimelineEvent]
    dispatches: list[PortalDispatch]
