import datetime as dt

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.enums import Verdict
from app.db.session import get_db
from app.modules.qclog import schemas as s
from app.modules.qclog import service

router = APIRouter(prefix="/qc/log", tags=["qc"], dependencies=[Depends(require_roles("qc", "owner", "supervisor"))])


@router.get("", response_model=s.LogPage)
def photo_log(
    order: str | None = Query(None, max_length=60, description="order code, buyer or fabric"),
    lot: str | None = Query(None, max_length=30, description="yarn lot (batch) code"),
    verdict: Verdict | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    overrode_ai: bool | None = None,
    with_photo: bool = True,
    sort: Literal["newest", "oldest", "order", "batch"] = "newest",
    q: str | None = Query(None, max_length=60),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> s.LogPage:
    return service.log_page(db, limit=limit, offset=offset, order=order, lot=lot, verdict=verdict, date_from=date_from,
                            date_to=date_to, overrode=overrode_ai, with_photo=with_photo, q=q, sort=sort)


@router.get("/filters", response_model=s.LogFilters)
def log_filters(db: Session = Depends(get_db)) -> s.LogFilters:
    return service.filter_options(db)
