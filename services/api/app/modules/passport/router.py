from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import ALL_ROLES, require_roles
from app.db.models import User
from app.db.session import get_db
from app.modules.passport import service
from app.modules.passport.schemas import Passport
from app.modules.passport.service import buyer_view  # noqa: F401  (kept importable from here)

router = APIRouter(tags=["rolls"])


@router.get("/rolls/{roll_code}/passport", response_model=Passport)
def roll_passport(roll_code: str, db: Session = Depends(get_db),
                  user: User = Depends(require_roles(*ALL_ROLES))) -> Passport:
    return service.get_passport(db, user, roll_code)
