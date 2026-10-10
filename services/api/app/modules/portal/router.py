from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.models import User
from app.db.session import get_db
from app.modules.portal import schemas as s
from app.modules.portal import service

router = APIRouter(prefix="/portal", tags=["portal"])
buyer_only = require_roles("buyer")


@router.get("/orders", response_model=list[s.PortalOrder])
def my_orders(db: Session = Depends(get_db), user: User = Depends(buyer_only)) -> list[s.PortalOrder]:
    return service.my_orders(db, user)


@router.get("/orders/{order_code}", response_model=s.PortalOrderDetail)
def my_order(order_code: str, db: Session = Depends(get_db), user: User = Depends(buyer_only)) -> s.PortalOrderDetail:
    return service.my_order(db, user, order_code)
