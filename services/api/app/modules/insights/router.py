from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.modules.insights import examples as ex
from app.modules.insights import schemas as s

router = APIRouter(tags=["insights"])
planners = require_roles("owner", "accountant", "supervisor")
stock_planners = require_roles("owner", "accountant", "supervisor", "store")


@router.get("/insights/late-orders", response_model=list[s.EtaOut], dependencies=[Depends(planners)])
def late_orders() -> list[s.EtaOut]:
    return [ex.ETA]


@router.get("/orders/{order_code}/eta", response_model=s.EtaOut, dependencies=[Depends(planners)])
def order_eta(order_code: str) -> s.EtaOut:
    return ex.ETA


@router.get("/insights/shortages", response_model=list[s.ShortageOut], dependencies=[Depends(stock_planners)])
def shortages() -> list[s.ShortageOut]:
    return [ex.SHORTAGE]


@router.get("/insights/root-causes", response_model=list[s.RootCauseRow], dependencies=[Depends(planners)])
def root_causes() -> list[s.RootCauseRow]:
    return ex.ROOT_CAUSES
