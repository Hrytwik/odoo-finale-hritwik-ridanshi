from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.modules.costing import examples as ex
from app.modules.costing import service
from app.modules.costing.schemas import MonthReport, OrderCost, RollCost

router = APIRouter(tags=["costing"])
finance = require_roles(*service.FINANCE)
Month = Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


@router.get("/costing/rolls/{roll_code}", response_model=RollCost, dependencies=[Depends(finance)])
def roll_cost(roll_code: str, db: Session = Depends(get_db)) -> RollCost:
    return service.roll_cost(db, roll_code)


@router.get("/costing/orders/{order_code}", response_model=OrderCost, dependencies=[Depends(finance)])
def order_cost(order_code: str, db: Session = Depends(get_db)) -> OrderCost:
    return service.order_cost(db, order_code)


@router.get("/reports/month", response_model=MonthReport, dependencies=[Depends(finance)])
def month_report(month: Month) -> MonthReport:
    return ex.MONTH.model_copy(update={"month": month})
