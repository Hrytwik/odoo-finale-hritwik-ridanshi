from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.enums import RunStage
from app.db.session import get_db
from app.modules.floor import board
from app.modules.floor import examples as ex
from app.modules.floor import rolls as floor_rolls
from app.modules.floor import service
from app.modules.floor import schemas as s
from app.modules.rolls import service as roll_service
from app.modules.rolls.schemas import RollOut

router = APIRouter(tags=["floor"])
viewers = require_roles("supervisor", "owner", "accountant")
operators = require_roles("supervisor", "owner")


@router.get("/floor", response_model=s.FloorBoard, dependencies=[Depends(viewers)])
def floor_board(db: Session = Depends(get_db)) -> s.FloorBoard:
    return board.floor_board(db)


@router.get("/machines/{machine_code}", response_model=s.MachineDetail, dependencies=[Depends(viewers)])
def machine_detail(machine_code: str, db: Session = Depends(get_db)) -> s.MachineDetail:
    return board.machine_detail(db, machine_code)


@router.get("/runs", response_model=list[s.RunOut], dependencies=[Depends(viewers)])
def list_runs(stage: RunStage | None = None, order_code: str | None = None,
              db: Session = Depends(get_db)) -> list[s.RunOut]:
    return board.list_runs(db, stage, order_code)


@router.post("/runs", response_model=s.RunOut, status_code=201, dependencies=[Depends(operators)])
def start_run(body: s.RunStartIn, db: Session = Depends(get_db)) -> s.RunOut:
    return board.run_out(db, service.start_run(db, body))


@router.post("/runs/{run_id}/end", response_model=s.RunOut, dependencies=[Depends(operators)])
def end_run(run_id: int, body: s.RunEndIn, db: Session = Depends(get_db)) -> s.RunOut:
    return board.run_out(db, service.end_run(db, run_id, body))


@router.post("/runs/{run_id}/handover", response_model=s.RunOut, status_code=201, dependencies=[Depends(operators)])
def handover(run_id: int, body: s.HandoverIn, db: Session = Depends(get_db)) -> s.RunOut:
    return board.run_out(db, service.handover(db, run_id, body))


@router.post("/runs/{run_id}/rolls", response_model=RollOut, status_code=201, dependencies=[Depends(operators)])
def roll_off(run_id: int, body: s.RollOffIn, db: Session = Depends(get_db)) -> RollOut:
    return roll_service.roll_out(db, floor_rolls.roll_off(db, run_id, body))


@router.post("/runs/{run_id}/load-rolls", response_model=s.RunOut, dependencies=[Depends(operators)])
def load_rolls(run_id: int, body: s.LoadRollsIn, db: Session = Depends(get_db)) -> s.RunOut:
    return board.run_out(db, floor_rolls.load_rolls(db, run_id, body))


@router.post("/machines/{machine_code}/breakdown", response_model=s.MachineCard, dependencies=[Depends(operators)])
def breakdown(machine_code: str, body: s.BreakdownIn, db: Session = Depends(get_db)) -> s.MachineCard:
    return board.machine_card(db, service.breakdown(db, machine_code, body))


@router.post("/machines/{machine_code}/repair", response_model=s.MachineCard, dependencies=[Depends(operators)])
def repair(machine_code: str, db: Session = Depends(get_db)) -> s.MachineCard:
    return board.machine_card(db, service.repair(db, machine_code))
