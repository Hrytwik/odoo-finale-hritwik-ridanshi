from fastapi import APIRouter, Depends

from app.core.auth import ALL_ROLES, require_roles
from app.core.schemas import Ref
from app.db.models import User
from app.modules.passport import examples as ex
from app.modules.passport.schemas import Passport

router = APIRouter(tags=["rolls"])


def buyer_view(passport: Passport) -> Passport:
    """What a buyer may see: status, order, quality checks and dispatch. No cost, yarn lots, suppliers, machines,
    operators, inspector names, photos or AI output."""
    return passport.model_copy(update={
        "cost": None,
        "yarn_lots": [],
        "runs": [],
        "inspections": [
            i.model_copy(update={"inspector": Ref(id=0, name="Quality team"), "ai_suggestion": None, "photo_url": None})
            for i in passport.inspections
        ],
    })


@router.get("/rolls/{roll_code}/passport", response_model=Passport)
def roll_passport(roll_code: str, user: User = Depends(require_roles(*ALL_ROLES))) -> Passport:
    return buyer_view(ex.PASSPORT) if user.role == "buyer" else ex.PASSPORT
