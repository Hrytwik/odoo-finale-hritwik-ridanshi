from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.modules.orders import examples as ex
from app.modules.orders import schemas as s

router = APIRouter(prefix="/orders", tags=["orders"])
readers = require_roles("owner", "accountant", "supervisor", "store")
writers = require_roles("owner", "accountant")


@router.get("", response_model=list[s.OrderOut], dependencies=[Depends(readers)])
def list_orders(state: str | None = None, buyer_id: int | None = None) -> list[s.OrderOut]:
    return [ex.ORDER, ex.DRAFT]


@router.post("", response_model=s.OrderOut, status_code=201, dependencies=[Depends(writers)])
def create_order(body: s.OrderIn) -> s.OrderOut:
    return ex.DRAFT


@router.get("/{order_code}", response_model=s.OrderOut, dependencies=[Depends(readers)])
def get_order(order_code: str) -> s.OrderOut:
    return ex.ORDER


@router.post("/{order_code}/confirm", response_model=s.OrderOut, dependencies=[Depends(writers)])
def confirm_order(order_code: str) -> s.OrderOut:
    return ex.ORDER


@router.post("/{order_code}/cancel", response_model=s.OrderOut, dependencies=[Depends(writers)])
def cancel_order(order_code: str) -> s.OrderOut:
    return ex.DRAFT.model_copy(update={"state": "cancelled", "stage": "cancelled"})


@router.patch("/{order_code}", response_model=s.OrderOut, dependencies=[Depends(writers)])
def change_deadline(order_code: str, body: s.DeadlineIn) -> s.OrderOut:
    return ex.ORDER.model_copy(update={"deadline": body.deadline})


@router.get("/{order_code}/yarn-check", response_model=s.YarnCheckOut, dependencies=[Depends(readers)])
def yarn_check(order_code: str) -> s.YarnCheckOut:
    return ex.YARN_CHECK
