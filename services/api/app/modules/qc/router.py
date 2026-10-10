from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.models import User
from app.db.session import get_db
from app.modules.floor import board
from app.modules.floor.schemas import RunOut
from app.modules.qc import examples as ex
from app.modules.qc import schemas as s
from app.modules.qc import service

router = APIRouter(tags=["qc"])
inspectors = require_roles("qc", "owner")
queue_viewers = require_roles("qc", "owner", "supervisor")
rework_starters = require_roles("supervisor", "qc", "owner")


@router.get("/qc/queue", response_model=s.QcQueue, dependencies=[Depends(queue_viewers)])
def qc_queue(db: Session = Depends(get_db)) -> s.QcQueue:
    return service.queue(db)


@router.post("/qc/analyze", response_model=s.AnalyzeOut, dependencies=[Depends(inspectors)])
def analyze(body: s.AnalyzeIn) -> s.AnalyzeOut:
    return ex.ANALYZE


@router.post("/qc/inspections", response_model=s.InspectionOut, status_code=201)
def record_inspection(body: s.InspectionIn, db: Session = Depends(get_db),
                      user: User = Depends(inspectors)) -> s.InspectionOut:
    return service.inspection_out(db, service.record_inspection(db, user, body))


@router.post("/rework-runs", response_model=RunOut, status_code=201, dependencies=[Depends(rework_starters)])
def start_rework(body: s.ReworkIn, db: Session = Depends(get_db)) -> RunOut:
    return board.run_out(db, service.start_rework(db, body))


@router.get("/qc/model-card", response_model=s.ModelCard, dependencies=[Depends(queue_viewers)])
def model_card() -> s.ModelCard:
    return ex.MODEL_CARD
