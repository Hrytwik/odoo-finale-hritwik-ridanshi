from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.modules.floor import examples as ex
from app.modules.floor import schemas as s
from app.modules.rolls.schemas import RollOut

router = APIRouter(tags=["floor"])
viewers = require_roles("supervisor", "owner", "accountant")
operators = require_roles("supervisor", "owner")


@router.get("/floor", response_model=s.FloorBoard, dependencies=[Depends(viewers)])
def floor_board() -> s.FloorBoard:
    return ex.BOARD


@router.get("/machines/{machine_code}", response_model=s.MachineDetail, dependencies=[Depends(viewers)])
def machine_detail(machine_code: str) -> s.MachineDetail:
    return ex.DETAIL


@router.post("/runs", response_model=s.RunOut, status_code=201, dependencies=[Depends(operators)])
def start_run(body: s.RunStartIn) -> s.RunOut:
    return ex.RUN


@router.post("/runs/{run_id}/end", response_model=s.RunOut, dependencies=[Depends(operators)])
def end_run(run_id: int, body: s.RunEndIn) -> s.RunOut:
    return ex.RUN.model_copy(update={"ended_at": ex.NOW})


@router.post("/runs/{run_id}/handover", response_model=s.RunOut, status_code=201, dependencies=[Depends(operators)])
def handover(run_id: int, body: s.HandoverIn) -> s.RunOut:
    return ex.RUN.model_copy(update={"id": run_id + 1, "started_at": ex.NOW, "roll_codes": [], "metres": 0})


@router.post("/runs/{run_id}/rolls", response_model=RollOut, status_code=201, dependencies=[Depends(operators)])
def roll_off(run_id: int, body: s.RollOffIn) -> RollOut:
    return ex.ROLL.model_copy(update={"metres": body.metres})


@router.post("/runs/{run_id}/load-rolls", response_model=s.RunOut, dependencies=[Depends(operators)])
def load_rolls(run_id: int, body: s.LoadRollsIn) -> s.RunOut:
    return ex.RUN.model_copy(update={"id": run_id, "stage": "dyeing", "machine_code": "DYE-01",
                                     "roll_codes": body.roll_codes})


@router.post("/machines/{machine_code}/breakdown", response_model=s.MachineCard, dependencies=[Depends(operators)])
def breakdown(machine_code: str, body: s.BreakdownIn) -> s.MachineCard:
    return ex.CARDS[2]


@router.post("/machines/{machine_code}/repair", response_model=s.MachineCard, dependencies=[Depends(operators)])
def repair(machine_code: str) -> s.MachineCard:
    return ex.CARDS[2].model_copy(update={"status": "idle", "downtime": None})
