import datetime as dt

from app.core.enums import RollStatus
from app.core.schemas import Out


class RollOut(Out):
    id: int
    code: str
    order_code: str
    buyer_name: str
    fabric: str
    colour: str
    metres: float
    status: RollStatus
    created_at: dt.datetime
