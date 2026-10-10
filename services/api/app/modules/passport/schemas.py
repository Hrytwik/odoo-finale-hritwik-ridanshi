import datetime as dt

from app.core.enums import RunStage
from app.core.schemas import Out
from app.modules.costing.schemas import RollCost
from app.modules.qc.schemas import InspectionOut
from app.modules.rolls.schemas import RollOut


class PassportLot(Out):
    lot_code: str
    yarn_type: str
    supplier: str
    is_blocked: bool


class PassportRun(Out):
    id: int
    stage: RunStage
    machine_code: str | None
    machine_name: str | None
    operator: str
    started_at: dt.datetime
    ended_at: dt.datetime | None


class PassportDispatch(Out):
    code: str
    dispatched_at: dt.datetime | None
    vehicle_no: str
    invoice_no: str | None


class Passport(Out):
    roll: RollOut
    order_code: str
    buyer_name: str
    deadline: dt.date
    yarn_lots: list[PassportLot]
    runs: list[PassportRun]
    inspections: list[InspectionOut]
    cost: RollCost | None
    dispatch: PassportDispatch | None
