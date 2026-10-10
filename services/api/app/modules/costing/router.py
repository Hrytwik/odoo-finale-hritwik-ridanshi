from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth import require_roles
from app.modules.costing import examples as ex
from app.modules.costing.schemas import MonthReport, OrderCost, RollCost

router = APIRouter(tags=["costing"])
finance = require_roles("owner", "accountant")
Month = Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


@router.get("/costing/rolls/{roll_code}", response_model=RollCost, dependencies=[Depends(finance)])
def roll_cost(roll_code: str) -> RollCost:
    return ex.ROLL_COST


@router.get("/costing/orders/{order_code}", response_model=OrderCost, dependencies=[Depends(finance)])
def order_cost(order_code: str) -> OrderCost:
    return ex.ORDER_COST


@router.get("/reports/month", response_model=MonthReport, dependencies=[Depends(finance)])
def month_report(month: Month) -> MonthReport:
    return ex.MONTH.model_copy(update={"month": month})
