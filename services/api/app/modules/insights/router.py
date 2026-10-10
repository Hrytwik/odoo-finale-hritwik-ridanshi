from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.modules.insights import schemas as s
from app.modules.insights import service

router = APIRouter(tags=["insights"])
planners = require_roles("owner", "accountant", "supervisor")
stock_planners = require_roles("owner", "accountant", "supervisor", "store")


@router.get("/insights/late-orders", response_model=list[s.EtaOut], dependencies=[Depends(planners)])
def late_orders(db: Session = Depends(get_db)) -> list[s.EtaOut]:
    return service.late_orders(db)


@router.get("/orders/{order_code}/eta", response_model=s.EtaOut, dependencies=[Depends(planners)])
def order_eta(order_code: str, db: Session = Depends(get_db)) -> s.EtaOut:
    return service.order_eta(db, order_code)


@router.get("/insights/shortages", response_model=list[s.ShortageOut], dependencies=[Depends(stock_planners)])
def shortages(db: Session = Depends(get_db)) -> list[s.ShortageOut]:
    return service.shortages(db)


@router.get("/insights/root-causes", response_model=list[s.RootCauseRow], dependencies=[Depends(planners)])
def root_causes(db: Session = Depends(get_db)) -> list[s.RootCauseRow]:
    return service.root_causes(db)
