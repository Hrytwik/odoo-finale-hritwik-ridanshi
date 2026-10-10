from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.modules.floor import examples as floor_ex
from app.modules.floor.schemas import RunOut
from app.modules.qc import examples as ex
from app.modules.qc import schemas as s

router = APIRouter(tags=["qc"])
inspectors = require_roles("qc", "owner")
queue_viewers = require_roles("qc", "owner", "supervisor")
rework_starters = require_roles("supervisor", "qc", "owner")


@router.get("/qc/queue", response_model=s.QcQueue, dependencies=[Depends(queue_viewers)])
def qc_queue() -> s.QcQueue:
    return ex.QUEUE


@router.post("/qc/analyze", response_model=s.AnalyzeOut, dependencies=[Depends(inspectors)])
def analyze(body: s.AnalyzeIn) -> s.AnalyzeOut:
    return ex.ANALYZE


@router.post("/qc/inspections", response_model=s.InspectionOut, status_code=201, dependencies=[Depends(inspectors)])
def record_inspection(body: s.InspectionIn) -> s.InspectionOut:
    return ex.INSPECTION


@router.post("/rework-runs", response_model=RunOut, status_code=201, dependencies=[Depends(rework_starters)])
def start_rework(body: s.ReworkIn) -> RunOut:
    return floor_ex.RUN.model_copy(update={"stage": "rework", "machine_code": body.machine_code,
                                           "roll_codes": [body.roll_code], "input_run_id": None})


@router.get("/qc/model-card", response_model=s.ModelCard, dependencies=[Depends(queue_viewers)])
def model_card() -> s.ModelCard:
    return ex.MODEL_CARD
