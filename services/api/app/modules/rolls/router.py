from fastapi import APIRouter, Depends

from app.core.auth import STAFF, require_roles
from app.core.enums import RollStatus
from app.modules.floor.examples import ROLL
from app.modules.rolls.schemas import RollOut

router = APIRouter(tags=["rolls"])

EXAMPLE_ROLLS = [ROLL, ROLL.model_copy(update={"id": 143, "code": "R-0143"})]


@router.get("/rolls", response_model=list[RollOut], dependencies=[Depends(require_roles(*STAFF))])
def list_rolls(status: RollStatus | None = None, order_code: str | None = None) -> list[RollOut]:
    return [r for r in EXAMPLE_ROLLS
            if (status is None or r.status == status) and (order_code is None or r.order_code == order_code)]
