"""The photo log: every quality check, newest first, with its photo, the model's guess, the inspector's verdict and remark,
and the order and yarn lot (batch) it belongs to. Read only: checks are recorded through the QC screens."""
import datetime as dt

from sqlalchemy import and_, bindparam, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.db.models import Buyer, FabricType, Order, QcInspection, Roll, Worker
from app.modules.qc.schemas import AiSuggestion, DefectOut
from app.modules.qclog import schemas as s

IST = "Asia/Kolkata"

# The yarn lots a roll was woven from: lots with a net positive issue to the spinning run that fed its weaving run.
_ROLL_LOTS = text("""
SELECT rr.roll_id, l.lot_code
FROM roll_runs rr
JOIN production_runs w ON w.id = rr.run_id AND w.stage = 'weaving'
JOIN yarn_movements m ON m.production_run_id = w.input_run_id AND m.kind IN ('issue', 'return')
JOIN yarn_lots l ON l.id = m.yarn_lot_id
WHERE rr.roll_id IN :ids
GROUP BY rr.roll_id, l.lot_code
HAVING SUM(m.qty_kg) < 0
ORDER BY rr.roll_id, l.lot_code
""").bindparams(bindparam("ids", expanding=True))

_LOT_ROLLS = text("""
SELECT rr.roll_id
FROM roll_runs rr
JOIN production_runs w ON w.id = rr.run_id AND w.stage = 'weaving'
JOIN yarn_movements m ON m.production_run_id = w.input_run_id AND m.kind IN ('issue', 'return')
JOIN yarn_lots l ON l.id = m.yarn_lot_id
WHERE l.lot_code = :lot
GROUP BY rr.roll_id, l.id
HAVING SUM(m.qty_kg) < 0
""")


def _like(text_in: str) -> str:
    escaped = text_in.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    return f"%{escaped}%"


def _lots_for(db: Session, roll_ids: list[int]) -> dict[int, list[str]]:
    if not roll_ids:
        return {}
    out: dict[int, list[str]] = {}
    for roll_id, lot_code in db.execute(_ROLL_LOTS, {"ids": roll_ids}):
        out.setdefault(roll_id, []).append(lot_code)
    return out


def _conditions(db: Session, *, order: str | None, lot: str | None, verdict: str | None, date_from: dt.date | None,
                date_to: dt.date | None, overrode: bool | None, with_photo: bool, q: str | None) -> list | None:
    """The WHERE parts for the chosen filters, or None when a filter can match nothing (an unknown lot)."""
    conds = []
    if with_photo:
        conds.append(QcInspection.photo_path.is_not(None))
    if order and order.strip():
        like = _like(order.strip())
        conds.append(or_(Order.code.ilike(like, escape="\\"), Buyer.name.ilike(like, escape="\\"),
                         FabricType.name.ilike(like, escape="\\")))
    if lot and lot.strip():
        ids = [row[0] for row in db.execute(_LOT_ROLLS, {"lot": lot.strip()})]
        if not ids:
            return None
        conds.append(Roll.id.in_(ids))
    if verdict:
        conds.append(QcInspection.verdict == verdict)
    day = func.date(func.timezone(IST, QcInspection.inspected_at))
    if date_from:
        conds.append(day >= date_from)
    if date_to:
        conds.append(day <= date_to)
    if overrode:
        conds.append(QcInspection.overrode_ai.is_(True))
    if q and q.strip():
        like = _like(q.strip())
        conds.append(or_(Roll.code.ilike(like, escape="\\"), Order.code.ilike(like, escape="\\"),
                         Buyer.name.ilike(like, escape="\\"), QcInspection.notes.ilike(like, escape="\\")))
    return conds


def _joined(stmt):
    return (stmt.join(Roll, Roll.id == QcInspection.roll_id).join(Order, Order.id == Roll.order_id)
            .join(Buyer, Buyer.id == Order.buyer_id).join(FabricType, FabricType.id == Order.fabric_type_id)
            .join(Worker, Worker.id == QcInspection.inspector_worker_id))


def log_page(db: Session, *, limit: int, offset: int, **filters) -> s.LogPage:
    conds = _conditions(db, **filters)
    if conds is None:
        return s.LogPage(items=[], counts=s.LogCounts(total=0, passed=0, rework=0, rejected=0, overrode_ai=0),
                         limit=limit, offset=offset)
    where = and_(*conds) if conds else True

    rows = db.execute(
        _joined(select(QcInspection, Roll, Order, Buyer, FabricType, Worker).options(selectinload(QcInspection.defects)))
        .where(where).order_by(QcInspection.inspected_at.desc(), QcInspection.id.desc()).limit(limit).offset(offset)
    ).all()
    lots = _lots_for(db, [roll.id for _, roll, *_ in rows])

    tally = {verdict: (n, over) for verdict, n, over in db.execute(
        _joined(select(QcInspection.verdict, func.count(), func.count().filter(QcInspection.overrode_ai.is_(True))))
        .where(where).group_by(QcInspection.verdict))}

    def count(verdict: str) -> int:
        return tally.get(verdict, (0, 0))[0]

    counts = s.LogCounts(total=sum(n for n, _ in tally.values()), passed=count("pass"), rework=count("rework"),
                         rejected=count("reject"), overrode_ai=sum(over for _, over in tally.values()))

    items = [
        s.LogItem(
            id=insp.id, roll_code=roll.code, order_code=order.code, buyer_name=buyer.name, fabric=fabric.name,
            colour=order.colour, metres=float(roll.metres), lots=lots.get(roll.id, []), inspector=worker.name,
            inspected_at=insp.inspected_at, verdict=insp.verdict, overrode_ai=insp.overrode_ai,
            defects=[DefectOut(defect_type=d.defect_type, count=d.count, ai_detected=d.ai_detected) for d in insp.defects],
            remark=insp.notes, photo_url=f"/api/{insp.photo_path}" if insp.photo_path else None,
            ai=AiSuggestion.model_validate(insp.ai_suggestion) if insp.ai_suggestion else None,
        )
        for insp, roll, order, buyer, fabric, worker in rows
    ]
    return s.LogPage(items=items, counts=counts, limit=limit, offset=offset)


def filter_options(db: Session) -> s.LogFilters:
    """The orders and yarn lots that have a checked roll, so the filter lists only offer choices that can match."""
    orders = db.execute(
        select(Order.code, Buyer.name).select_from(QcInspection)
        .join(Roll, Roll.id == QcInspection.roll_id).join(Order, Order.id == Roll.order_id)
        .join(Buyer, Buyer.id == Order.buyer_id).distinct().order_by(Order.code.desc())).all()
    roll_ids = [r for (r,) in db.execute(select(QcInspection.roll_id).distinct())]
    lots = sorted({code for codes in _lots_for(db, roll_ids).values() for code in codes}, reverse=True)
    return s.LogFilters(orders=[s.OrderOption(code=c, buyer_name=b) for c, b in orders], lots=lots)
