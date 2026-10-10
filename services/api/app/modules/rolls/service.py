"""Roll reads. The status of a roll is never stored: it comes from the v_roll_status view (spec §5)."""
from sqlalchemy import column, select, table
from sqlalchemy.orm import Session, selectinload

from app.core.money import to_float
from app.db.models import Order, Roll
from app.modules.rolls.schemas import RollOut

v_roll_status = table("v_roll_status", column("roll_id"), column("status"))


def roll_outs(db: Session, rolls: list[Roll]) -> list[RollOut]:
    if not rolls:
        return []
    status = dict(db.execute(select(v_roll_status.c.roll_id, v_roll_status.c.status)
                             .where(v_roll_status.c.roll_id.in_([r.id for r in rolls]))).all())
    return [RollOut(id=r.id, code=r.code, order_code=r.order.code, buyer_name=r.order.buyer.name,
                    fabric=r.order.fabric_type.name, colour=r.order.colour, metres=to_float(r.metres),
                    status=status[r.id], created_at=r.created_at) for r in rolls]


def roll_out(db: Session, roll: Roll) -> RollOut:
    return roll_outs(db, [roll])[0]


def list_rolls(db: Session, status: str | None = None, order_code: str | None = None) -> list[RollOut]:
    query = (select(Roll).options(selectinload(Roll.order).selectinload(Order.buyer),
                                  selectinload(Roll.order).selectinload(Order.fabric_type))
             .order_by(Roll.id.desc()))
    if status is not None:
        query = query.join(v_roll_status, v_roll_status.c.roll_id == Roll.id).where(v_roll_status.c.status == status)
    if order_code is not None:
        query = query.join(Order, Order.id == Roll.order_id).where(Order.code == order_code)
    return roll_outs(db, list(db.scalars(query)))


def roll_status(db: Session, roll_id: int) -> str:
    """The roll's status from v_roll_status (read it AFTER taking the roll's row lock when a rule depends on it)."""
    return db.scalar(select(v_roll_status.c.status).where(v_roll_status.c.roll_id == roll_id))
