"""Delay notices: the owner picks a reason from a short list, a sentence is drafted for the buyer, the owner may edit it,
and on sending it appears in that buyer's bell and, when WhatsApp is connected, on their WhatsApp too. A buyer sees only
notices for their own orders. A WhatsApp problem never stops the bell notice."""
import datetime as dt

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.db.models import BuyerNotice, Dispatch, Invoice, MessagingSettings, Order, User
from app.modules.llm import crypto
from app.modules.llm.runtime import build_adapter, load_config
from app.modules.llm.types import AdapterError, Turn
from app.modules.notices import schemas as s
from app.modules.notices import whatsapp
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
    "dispatched": ("Order dispatched", ""),
}

SYSTEM = (
    "You write short, polite notices from a textile mill to a buyer. Write one or two sentences. Say that the order is delayed "
    "and why, in plain words. Do not mention machines, workers, costs, prices or other buyers. Do not promise a new date. "
    "Reply with the notice only."
)

_PLAIN = {ord(c): "-" for c in "‐‑‒–"} | {ord(c): " " for c in "   "}


def plain(text: str) -> str:
    """Hyphens and spaces as ordinary characters, so an order code in the text can be copied and searched."""
    return text.translate(_PLAIN)


def _template(order: Order, reason: str) -> str:
    return (f"Your order {order.code} may be delayed because {REASONS[reason][1]}. "
            "We are working to get it to you as soon as we can and will keep you updated here.")


def channel(db: Session, order: Order) -> s.ChannelOut:
    """What the owner is told about WhatsApp for this buyer before sending: where it would go, or why it would not."""
    config = whatsapp.load_config(db)
    number = whatsapp.normalise_phone(order.buyer.phone)
    tracking = f"{config.public_url.rstrip('/')}/portal/orders/{order.code}" if config.public_url else None
    if not config.ready:
        problem = "WhatsApp is not connected yet (owner: AI > WhatsApp)." if not config.enabled else "WhatsApp is switched on but its details are incomplete."
    elif not order.buyer.phone or not order.buyer.phone.strip():
        problem = f"{order.buyer.name} has no phone number. Add one under Buyers."
    elif number is None:
        problem = f"The phone number for {order.buyer.name} does not look right. Fix it under Buyers."
    else:
        problem = None
    return s.ChannelOut(whatsapp_ready=problem is None, to=whatsapp.mask_phone(number) if number else None,
                        phone=number.lstrip("+") if number else None, problem=problem, tracking_url=tracking)


def draft(db: Session, order_code: str, reason: str) -> s.DraftOut:
    """A sentence for the buyer. Written by the language model when one is set up, otherwise from a fixed template."""
    order = get_order_or_404(db, order_code)
    info = channel(db, order)
    config = load_config(db)
    if config.configured:
        prompt = (f"Order {order.code}, {order.fabric_type.name} in {order.colour}, promised for {order.deadline:%d %B %Y}. "
                  f"Reason for the delay: {REASONS[reason][0]}.")
        adapter = build_adapter(config)
        text = ""
        for budget in (700, 1400):  # a model that thinks first may need more room; a cut-off sentence is never shown
            try:
                reply = adapter.complete(SYSTEM, [Turn(role="user", text=prompt)], [], {"max_tokens": budget})
            except AdapterError:
                break
            if not reply.truncated:
                text = reply.text.strip()
                break
        if text:
            return s.DraftOut(message=plain(text)[:400], drafted_by_ai=True, channel=info)
    return s.DraftOut(message=_template(order, reason), drafted_by_ai=False, channel=info)


def _out(notice: BuyerNotice, order_code: str) -> s.NoticeOut:
    return s.NoticeOut(id=notice.id, kind=notice.kind, order_code=order_code, reason=notice.reason, reason_label=REASONS[notice.reason][0],
                       message=notice.message, created_at=notice.created_at, read=notice.read_at is not None,
                       whatsapp_status=notice.whatsapp_status, whatsapp_detail=notice.whatsapp_detail)


def send(db: Session, user: User, order_code: str, body: s.NoticeIn) -> s.NoticeOut:
    order = get_order_or_404(db, order_code)
    if order.state != "confirmed":
        raise AppError("ORDER_NOT_CONFIRMED", "A delay notice can only be sent for a confirmed order", status=409)
    notice = BuyerNotice(order_id=order.id, buyer_id=order.buyer_id, kind="delay", reason=body.reason, message=body.message, sent_by=user.id)
    return _deliver(db, notice, order)


def _deliver(db: Session, notice: BuyerNotice, order: Order) -> s.NoticeOut:
    """Saves the notice for the buyer's bell, then also sends it on WhatsApp when that is connected and possible."""
    db.add(notice)
    commit(db)  # the bell notice is saved first: whatever happens on WhatsApp cannot lose it
    db.refresh(notice)
    broadcaster.publish("notice.changed", notice.id)

    config = whatsapp.load_config(db)
    number = whatsapp.normalise_phone(order.buyer.phone)
    info = channel(db, order)
    if info.problem:
        result = whatsapp.SendResult("skipped", info.problem)
    else:
        link = f"{config.public_url.rstrip('/')}/portal/orders/{order.code}" if config.public_url else None
        result = whatsapp.send_text(config, number or "", notice.message, link)
    notice.whatsapp_status, notice.whatsapp_detail, notice.whatsapp_sid = result.status, (result.detail or None), result.sid
    commit(db)
    db.refresh(notice)
    return _out(notice, order.code)


def inr(amount) -> str:
    """12345678.5 as 1,23,45,678.50, the way rupee amounts are written."""
    whole, _, fraction = f"{float(amount):.2f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "\u20b9" + ",".join(groups + [tail]) + "." + fraction


def notify_dispatched(db: Session, dispatch_code: str) -> list[s.NoticeOut]:
    """When a truck is confirmed: tell the buyer, for each of their orders on it, how much left the mill and the invoice.
    Facts only, so no model is involved. Called after the dispatch is saved; the caller never lets a failure here undo it."""
    dispatch = db.scalar(select(Dispatch).where(Dispatch.code == dispatch_code))
    invoice = db.scalar(select(Invoice).where(Invoice.dispatch_id == dispatch.id)) if dispatch else None
    if dispatch is None or invoice is None or dispatch.state != "dispatched":
        return []
    sent = []
    for line in sorted(invoice.lines, key=lambda ln: ln.order_id):
        order = db.get(Order, line.order_id)
        message = (f"{float(line.metres):g} m of your order {order.code} has left the mill on truck {dispatch.vehicle_no} "
                   f"(dispatch {dispatch.code}). Your invoice {invoice.invoice_no} is {inr(line.amount)}.")
        sent.append(_deliver(db, BuyerNotice(order_id=order.id, buyer_id=dispatch.buyer_id, kind="dispatch", reason="dispatched", message=message), order))
    return sent


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


# ---- the WhatsApp connection ----

def _settings_out(db: Session) -> s.MessagingSettingsOut:
    row = db.get(MessagingSettings, 1)
    config = whatsapp.load_config(db)
    return s.MessagingSettingsOut(account_sid=row.account_sid if row else None, token_set=bool(row and row.auth_token_encrypted),
                                  from_number=row.from_number if row else None, content_sid=row.content_sid if row else None,
                                  public_url=row.public_url if row else None,
                                  enabled=bool(row and row.enabled), ready=config.ready)


def get_settings(db: Session) -> s.MessagingSettingsOut:
    return _settings_out(db)


def save_settings(db: Session, user: User, body: s.MessagingSettingsIn) -> s.MessagingSettingsOut:
    row = db.get(MessagingSettings, 1)
    if row is None:
        row = MessagingSettings(id=1, provider="twilio_whatsapp", enabled=False)
        db.add(row)
    if body.account_sid is not None:
        row.account_sid = body.account_sid or None
    if body.from_number is not None:
        number = whatsapp.normalise_phone(body.from_number.removeprefix("whatsapp:")) if body.from_number else None
        if body.from_number and number is None:
            raise AppError("VALIDATION_ERROR", "That sender number does not look right. Use the full number, like +14155238886", field="from_number", status=422)
        row.from_number = number
    if body.content_sid is not None:
        sid = body.content_sid.strip()
        if sid and not (sid.startswith("HX") and len(sid) == 34):
            raise AppError("VALIDATION_ERROR", "A template ID starts with HX and is 34 characters long. Copy it from Twilio's Content Template Builder.", field="content_sid", status=422)
        row.content_sid = sid or None
    if body.public_url is not None:
        url = body.public_url.rstrip("/")
        if url and not url.startswith(("http://", "https://")):
            raise AppError("VALIDATION_ERROR", "The address must start with https:// (or http://)", field="public_url", status=422)
        row.public_url = url or None
    if body.auth_token is not None:
        row.auth_token_encrypted = crypto.encrypt_key(body.auth_token) if body.auth_token else None
    if body.enabled and not (row.account_sid and row.auth_token_encrypted and row.from_number):
        raise AppError("VALIDATION_ERROR", "To switch WhatsApp on, fill in the Account SID, the Auth Token and the sender number", field="enabled", status=422)
    row.enabled = body.enabled
    row.updated_by = user.id
    commit(db)
    return _settings_out(db)


def send_test(db: Session, body: s.TestIn) -> s.TestOut:
    """One short message to a phone, so the owner can see that the connection works."""
    number = whatsapp.normalise_phone(body.to)
    if number is None:
        raise AppError("VALIDATION_ERROR", "That phone number does not look right. Use the full number, like +91 98450 12345", field="to", status=422)
    config = whatsapp.load_config(db)
    result = whatsapp.send_text(config, number, "This is a test message from Everest Mills. WhatsApp is connected.", config.public_url)
    return s.TestOut(status=result.status, detail=result.detail, to=whatsapp.mask_phone(number))
