import datetime as dt

from app.core.schemas import Ref
from app.modules.floor.examples import NOW, ROLL
from app.modules.qc.schemas import (
    AiSuggestion, Box, DefectOut, InspectionOut, QcCounts, QcQueue,
)

SUGGESTION = AiSuggestion(model_version="example", verdict="rework", boxes=[
    Box(x=0.42, y=0.31, w=0.08, h=0.07, defect_type="hole", confidence=0.91),
])
INSPECTION = InspectionOut(
    id=301, roll_code="R-0142", inspector=Ref(id=2, name="Meena Devi"), inspected_at=NOW, verdict="rework",
    overrode_ai=False, defects=[DefectOut(defect_type="hole", count=1, ai_detected=True)], photo_url=None,
    ai_suggestion=SUGGESTION, notes=None,
)
QUEUE = QcQueue(
    counts=QcCounts(awaiting_qc=4, awaiting_rework=1, in_rework=0, passed=11, rejected=1),
    rolls=[ROLL.model_copy(update={"status": "awaiting_qc"})],
)
