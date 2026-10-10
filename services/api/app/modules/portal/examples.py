import datetime as dt

from app.modules.portal.schemas import PortalDispatch, PortalOrder, PortalOrderDetail, TimelineEvent

D = lambda day, hour=10: dt.datetime(2026, 10, day, hour, tzinfo=dt.UTC)  # noqa: E731

ORDER = PortalOrder(code="ORD-0012", fabric="Poplin 58in", colour="navy", qty_metres=5000, stage="weaving",
                    progress_pct=46.2, deadline=dt.date(2026, 10, 20), delivery_date=dt.date(2026, 10, 22))
DETAIL = PortalOrderDetail(
    **ORDER.model_dump(),
    timeline=[TimelineEvent(at=D(1), label="Order confirmed"), TimelineEvent(at=D(2), label="Spinning started"),
              TimelineEvent(at=D(4), label="Weaving started"), TimelineEvent(at=D(6), label="Dyeing started"),
              TimelineEvent(at=D(8), label="First rolls passed quality check"),
              TimelineEvent(at=D(9), label="330 m dispatched (DSP-0007)")],
    dispatches=[PortalDispatch(code="DSP-0007", dispatched_at=D(9), metres=330, invoice_no="INV-0007")],
)
