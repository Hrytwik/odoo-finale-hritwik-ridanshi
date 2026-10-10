from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.modules.orders import schemas as s
from app.modules.orders import service

router = APIRouter(prefix="/orders", tags=["orders"])
readers = require_roles("owner", "accountant", "supervisor", "store")
writers = require_roles("owner", "accountant")


@router.get("", response_model=list[s.OrderOut], dependencies=[Depends(readers)])
def list_orders(state: str | None = None, buyer_id: int | None = None,
                db: Session = Depends(get_db)) -> list[s.OrderOut]:
    return service.list_orders(db, state, buyer_id)


@router.post("", response_model=s.OrderOut, status_code=201, dependencies=[Depends(writers)])
def create_order(body: s.OrderIn, db: Session = Depends(get_db)) -> s.OrderOut:
    return service.order_out(db, service.create_order(db, body))


@router.get("/{order_code}", response_model=s.OrderOut, dependencies=[Depends(readers)])
def get_order(order_code: str, db: Session = Depends(get_db)) -> s.OrderOut:
    return service.order_out(db, service.get_order_or_404(db, order_code))


@router.post("/{order_code}/confirm", response_model=s.OrderOut, dependencies=[Depends(writers)])
def confirm_order(order_code: str, db: Session = Depends(get_db)) -> s.OrderOut:
    return service.order_out(db, service.confirm_order(db, order_code))


@router.post("/{order_code}/cancel", response_model=s.OrderOut, dependencies=[Depends(writers)])
def cancel_order(order_code: str, db: Session = Depends(get_db)) -> s.OrderOut:
    return service.order_out(db, service.cancel_order(db, order_code))


@router.patch("/{order_code}", response_model=s.OrderOut, dependencies=[Depends(writers)])
def change_deadline(order_code: str, body: s.DeadlineIn, db: Session = Depends(get_db)) -> s.OrderOut:
    return service.order_out(db, service.change_deadline(db, order_code, body))


@router.get("/{order_code}/yarn-check", response_model=s.YarnCheckOut, dependencies=[Depends(readers)])
def yarn_check(order_code: str, db: Session = Depends(get_db)) -> s.YarnCheckOut:
    return service.yarn_check(db, service.get_order_or_404(db, order_code))
