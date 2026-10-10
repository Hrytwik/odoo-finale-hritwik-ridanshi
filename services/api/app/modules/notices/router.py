from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.models import User
from app.db.session import get_db
from app.modules.notices import schemas as s
from app.modules.notices import service

router = APIRouter(tags=["notices"])
owner_only = require_roles("owner")
buyer_only = require_roles("buyer")


@router.post("/orders/{order_code}/delay-notice/draft", response_model=s.DraftOut, dependencies=[Depends(owner_only)])
def draft_notice(order_code: str, body: s.ReasonIn, db: Session = Depends(get_db)) -> s.DraftOut:
    """A sentence for the buyer, for the owner to read and edit before sending."""
    return service.draft(db, order_code, body.reason)


@router.post("/orders/{order_code}/delay-notice", response_model=s.NoticeOut, status_code=201)
def send_notice(order_code: str, body: s.NoticeIn, db: Session = Depends(get_db), user: User = Depends(owner_only)) -> s.NoticeOut:
    return service.send(db, user, order_code, body)


@router.get("/portal/notifications", response_model=s.NotificationsOut)
def my_notifications(db: Session = Depends(get_db), user: User = Depends(buyer_only)) -> s.NotificationsOut:
    return service.mine(db, user)


@router.post("/portal/notifications/read", response_model=s.NotificationsOut)
def read_notifications(db: Session = Depends(get_db), user: User = Depends(buyer_only)) -> s.NotificationsOut:
    return service.mark_all_read(db, user)
