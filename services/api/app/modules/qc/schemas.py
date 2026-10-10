import datetime as dt
from typing import Annotated

from pydantic import BaseModel, Field

from app.core.enums import DefectType, Verdict
from app.core.schemas import NonBlank, NoBool, OptText, Out, Ref
from app.modules.rolls.schemas import RollOut

Fraction = Annotated[float, Field(ge=0, le=1), NoBool]


class Box(BaseModel):
    x: Fraction
    y: Fraction
    w: Fraction
    h: Fraction
    defect_type: DefectType
    confidence: Fraction


class AiSuggestion(BaseModel):
    model_version: NonBlank
    verdict: Verdict
    boxes: Annotated[list[Box], Field(max_length=100)]


class AnalyzeIn(BaseModel):
    photo_path: NonBlank


class AnalyzeOut(Out):
    available: bool
    message: str | None
    suggestion: AiSuggestion | None


class DefectIn(BaseModel):
    defect_type: DefectType
    count: Annotated[int, Field(ge=1, le=1000)]
    ai_detected: bool = False


class InspectionIn(BaseModel):
    roll_code: NonBlank
    photo_path: NonBlank | None = None
    ai_suggestion: AiSuggestion | None = None
    verdict: Verdict
    defects: Annotated[list[DefectIn], Field(max_length=20)] = []
    notes: OptText = None


class DefectOut(Out):
    defect_type: DefectType
    count: int
    ai_detected: bool


class InspectionOut(Out):
    id: int
    roll_code: str
    inspector: Ref
    inspected_at: dt.datetime
    verdict: Verdict
    overrode_ai: bool
    defects: list[DefectOut]
    photo_url: str | None
    ai_suggestion: AiSuggestion | None
    notes: str | None


class QcCounts(Out):
    awaiting_qc: int
    awaiting_rework: int
    in_rework: int
    passed: int
    rejected: int


class QcQueue(Out):
    counts: QcCounts
    rolls: list[RollOut]


class ReworkIn(BaseModel):
    roll_code: NonBlank
    machine_code: NonBlank | None = None
    operator_worker_id: int


class DatasetRef(Out):
    name: str
    url: str
    licence: str


class ClassResult(Out):
    defect_type: DefectType
    found: int
    missed: int
    false_alarms: int
    precision: float | None
    recall: float | None


class ModelCard(Out):
    available: bool
    model_version: str | None
    trained_at: dt.datetime | None
    datasets: list[DatasetRef]
    test_defective: int
    test_clean: int
    clean_false_alarm_rate: float | None
    per_class: list[ClassResult]
    confusion_labels: list[str]
    confusion_matrix: list[list[int]]
