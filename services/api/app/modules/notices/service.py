"""Delay notices: the owner picks a reason from a short list, a sentence is drafted for the buyer, the owner may edit it,
and on sending it appears in that buyer's bell. A buyer sees only notices for their own orders."""
import datetime as dt

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.db.models import BuyerNotice, Order, User
from app.modules.llm.runtime import build_adapter, load_config
from app.modules.llm.types import AdapterError, Turn
from app.modules.notices import schemas as s
from app.modules.orders.service import get_order_or_404

# code -> (label shown to the owner, a plain phrase for the buyer that works inside "because ...")
REASONS: dict[str, tuple[str, str]] = {
    "yarn_shortage": ("Yarn shortage", "we are waiting for yarn to arrive"),
    "machine_breakdown": ("Machine breakdown", "one of our machines needs repair"),
    "power_cut": ("Power cut", "we lost production time to a power cut"),
    "staff_shortage": ("Staff shortage", "we are short of staff on the floor"),
    "quality_rework": ("Quality rework", "part of the fabric needs reworking to meet our quality standard"),
    "dye_delay": ("Dye or chemical delay", "our dyeing materials arrived late"),
    "transport": ("Transport problem", "there is a transport problem"),
    "buyer_change": ("Change to the order", "the order was changed"),
    "other": ("Other", "of an unexpected problem at the mill"),
}

SYSTEM = (
    "You write short, polite notices from a textile mill to a buyer. Write one or two sentences. Say that the order is delayed "
    "and why, in plain words. Do not mention machines, workers, costs, prices or other buyers. Do not promise a new date. "
    "Reply with the notice only."
)


def _template(order: Order, reason: str) -> str:
    return (f"Your order {order.code} may be delayed because {REASONS[reason][1]}. "
            "We are working to get it to you as soon as we can and will keep you updated here.")


def draft(db: Session, order_code: str, reason: str) -> s.DraftOut:
    """A sentence for the buyer. Written by the language model when one is set up, otherwise from a fixed template."""
    order = get_order_or_404(db, order_code)
    config = load_config(db)
    if config.configured:
        prompt = (f"Order {order.code}, {order.fabric_type.name} in {order.colour}, promised for {order.deadline:%d %B %Y}. "
                  f"Reason for the delay: {REASONS[reason][0]}.")
        try:
            text = build_adapter(config).complete(SYSTEM, [Turn(role="user", text=prompt)], [], {"max_tokens": 160}).text.strip()
        except AdapterError:
            text = ""
        if text:
            return s.DraftOut(message=text[:400], drafted_by_ai=True)
    return s.DraftOut(message=_template(order, reason), drafted_by_ai=False)


def _out(notice: BuyerNotice, order_code: str) -> s.NoticeOut:
    return s.NoticeOut(id=notice.id, order_code=order_code, reason=notice.reason, reason_label=REASONS[notice.reason][0],
                       message=notice.message, created_at=notice.created_at, read=notice.read_at is not None)


def send(db: Session, user: User, order_code: str, body: s.NoticeIn) -> s.NoticeOut:
    order = get_order_or_404(db, order_code)
    if order.state != "confirmed":
        raise AppError("ORDER_NOT_CONFIRMED", "A delay notice can only be sent for a confirmed order", status=409)
    notice = BuyerNotice(order_id=order.id, buyer_id=order.buyer_id, kind="delay", reason=body.reason, message=body.message, sent_by=user.id)
    db.add(notice)
    commit(db)
    db.refresh(notice)
    broadcaster.publish("notice.changed", notice.id)
    return _out(notice, order.code)


def mine(db: Session, user: User) -> s.NotificationsOut:
    rows = db.execute(select(BuyerNotice, Order.code).join(Order, Order.id == BuyerNotice.order_id)
                      .where(BuyerNotice.buyer_id == user.buyer_id)
                      .order_by(BuyerNotice.created_at.desc(), BuyerNotice.id.desc()).limit(50)).all()
    unread = db.scalar(select(func.count()).select_from(BuyerNotice)
                       .where(BuyerNotice.buyer_id == user.buyer_id, BuyerNotice.read_at.is_(None)))
    return s.NotificationsOut(unread=unread or 0, items=[_out(n, code) for n, code in rows])


def mark_all_read(db: Session, user: User) -> s.NotificationsOut:
    db.execute(update(BuyerNotice).where(BuyerNotice.buyer_id == user.buyer_id, BuyerNotice.read_at.is_(None))
               .values(read_at=dt.datetime.now(dt.UTC)))
    commit(db)
    return mine(db, user)
