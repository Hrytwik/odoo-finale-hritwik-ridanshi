from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.modules.portal import examples as ex
from app.modules.portal import schemas as s

router = APIRouter(prefix="/portal", tags=["portal"])
buyer_only = require_roles("buyer")


@router.get("/orders", response_model=list[s.PortalOrder], dependencies=[Depends(buyer_only)])
def my_orders() -> list[s.PortalOrder]:
    return [ex.ORDER]


@router.get("/orders/{order_code}", response_model=s.PortalOrderDetail, dependencies=[Depends(buyer_only)])
def my_order(order_code: str) -> s.PortalOrderDetail:
    return ex.DETAIL
