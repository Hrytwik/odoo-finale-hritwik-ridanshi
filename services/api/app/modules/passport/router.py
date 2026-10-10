from fastapi import APIRouter, Depends

from app.core.auth import ALL_ROLES, require_roles
from app.modules.passport import examples as ex
from app.modules.passport.schemas import Passport

router = APIRouter(tags=["rolls"])


@router.get("/rolls/{roll_code}/passport", response_model=Passport, dependencies=[Depends(require_roles(*ALL_ROLES))])
def roll_passport(roll_code: str) -> Passport:
    return ex.PASSPORT
