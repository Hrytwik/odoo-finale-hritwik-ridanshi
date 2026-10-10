"""Things other modules call after something happens, so a buyer is told. Each one is best effort: whatever goes wrong here is
logged and swallowed, because the thing that happened (a truck confirmed) must stand."""
import logging

from sqlalchemy.orm import Session

from app.modules.notices import service

log = logging.getLogger("everest.notices")


def after_dispatch_confirmed(db: Session, dispatch_code: str) -> None:
    try:
        service.notify_dispatched(db, dispatch_code)
    except Exception:  # noqa: BLE001 (a notice must never undo a dispatch)
        db.rollback()
        log.exception("could not notify the buyer about dispatch %s", dispatch_code)
