from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import STAFF, require_roles
from app.core.enums import RollStatus
from app.db.session import get_db
from app.modules.rolls import service
from app.modules.rolls.schemas import RollOut

router = APIRouter(tags=["rolls"])


@router.get("/rolls", response_model=list[RollOut], dependencies=[Depends(require_roles(*STAFF))])
def list_rolls(status: RollStatus | None = None, order_code: str | None = None,
               db: Session = Depends(get_db)) -> list[RollOut]:
    return service.list_rolls(db, status, order_code)
