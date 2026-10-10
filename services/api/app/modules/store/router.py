from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.models import User
from app.db.session import get_db
from app.modules.insights import recall
from app.modules.store import schemas as s
from app.modules.store import service

router = APIRouter(tags=["store"])
store_staff = require_roles("store", "owner")
issuers = require_roles("store", "supervisor", "owner")
stock_readers = require_roles("store", "owner", "supervisor", "accountant")


@router.post("/lots", response_model=s.LotOut, status_code=201)
def receive_lot(body: s.LotReceiveIn, db: Session = Depends(get_db), user: User = Depends(store_staff)) -> s.LotOut:
    return service.lot_out(db, service.receive_lot(db, user, body))


@router.get("/lots", response_model=list[s.LotOut], dependencies=[Depends(stock_readers)])
def list_lots(yarn_type_id: int | None = None, blocked: bool | None = None,
              db: Session = Depends(get_db)) -> list[s.LotOut]:
    return service.list_lots(db, yarn_type_id, blocked)


@router.get("/lots/{lot_code}", response_model=s.LotDetail, dependencies=[Depends(stock_readers)])
def get_lot(lot_code: str, db: Session = Depends(get_db)) -> s.LotDetail:
    return service.lot_detail(db, service.get_lot_or_404(db, lot_code))


@router.post("/lots/{lot_code}/block", response_model=s.LotOut)
def block_lot(lot_code: str, body: s.BlockIn, db: Session = Depends(get_db),
              user: User = Depends(store_staff)) -> s.LotOut:
    return service.lot_out(db, service.block_lot(db, user, lot_code, body))


@router.get("/lots/{lot_code}/recall", response_model=s.RecallOut, dependencies=[Depends(store_staff)])
def lot_recall(lot_code: str, db: Session = Depends(get_db)) -> s.RecallOut:
    return recall.lot_recall(db, lot_code)


@router.post("/movements/issue", response_model=s.MovementOut, status_code=201)
def issue_yarn(body: s.IssueIn, db: Session = Depends(get_db), user: User = Depends(issuers)) -> s.MovementOut:
    return service.movement_out(db, service.issue_yarn(db, user, body))


@router.post("/movements/return", response_model=s.MovementOut, status_code=201)
def return_yarn(body: s.ReturnIn, db: Session = Depends(get_db), user: User = Depends(issuers)) -> s.MovementOut:
    return service.movement_out(db, service.return_yarn(db, user, body))


@router.post("/movements/adjust", response_model=s.MovementOut, status_code=201)
def adjust_stock(body: s.AdjustIn, db: Session = Depends(get_db), user: User = Depends(store_staff)) -> s.MovementOut:
    return service.movement_out(db, service.adjust_stock(db, user, body))


@router.get("/stock", response_model=list[s.StockRow], dependencies=[Depends(stock_readers)])
def stock(db: Session = Depends(get_db)) -> list[s.StockRow]:
    return service.stock_rows(db)
