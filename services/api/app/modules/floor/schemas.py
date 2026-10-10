import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.enums import MachineStatus, RunStage, Stage
from app.core.schemas import NonBlank, NoBool, Out, PositiveQty, Ref


class RunBrief(Out):
    id: int
    order_code: str
    stage: RunStage
    operator: Ref
    started_at: dt.datetime
    order_progress_pct: float


class DowntimeOut(Out):
    reason: str
    started_at: dt.datetime


class MachineCard(Out):
    code: str
    name: str
    stage: Stage
    status: MachineStatus
    current_run: RunBrief | None
    downtime: DowntimeOut | None
    output_today: float
    output_unit: Literal["kg", "m"]


class FloorBoard(Out):
    machines: list[MachineCard]
    running: int
    idle: int
    down: int
    generated_at: dt.datetime


class RunOut(Out):
    id: int
    order_code: str
    machine_code: str | None
    stage: RunStage
    operator: Ref
    started_at: dt.datetime
    ended_at: dt.datetime | None
    output_kg: float | None
    input_run_id: int | None
    roll_codes: list[str]
    metres: float


class MachineDetail(MachineCard):
    recent_runs: list[RunOut]


class RunStartIn(BaseModel):
    order_code: NonBlank
    machine_code: NonBlank
    operator_worker_id: int
    input_run_id: int | None = None


class RunEndIn(BaseModel):
    output_kg: Annotated[float, Field(ge=0, le=1_000_000), NoBool] | None = None


class HandoverIn(BaseModel):
    operator_worker_id: int


class RollOffIn(BaseModel):
    metres: PositiveQty


class LoadRollsIn(BaseModel):
    roll_codes: Annotated[list[NonBlank], Field(min_length=1, max_length=200)]


class BreakdownIn(BaseModel):
    reason: NonBlank
