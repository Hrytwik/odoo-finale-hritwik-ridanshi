import datetime as dt

from app.core.schemas import Ref
from app.modules.floor.schemas import DowntimeOut, FloorBoard, MachineCard, MachineDetail, RunBrief, RunOut
from app.modules.rolls.schemas import RollOut

NOW = dt.datetime(2026, 10, 10, 11, 0, tzinfo=dt.UTC)
RAVI = Ref(id=1, name="Ravi Kumar")

RUN = RunOut(id=45, order_code="ORD-0012", machine_code="LOOM-04", stage="weaving", operator=RAVI,
             started_at=NOW - dt.timedelta(hours=3), ended_at=None, output_kg=None, input_run_id=41,
             roll_codes=["R-0142", "R-0143"], metres=220)
CARDS = [
    MachineCard(code="SPIN-01", name="Ring frame 1", stage="spinning", status="idle", current_run=None,
                downtime=None, output_today=587.5, output_unit="kg"),
    MachineCard(code="LOOM-04", name="Loom 4", stage="weaving", status="running",
                current_run=RunBrief(id=45, order_code="ORD-0012", stage="weaving", operator=RAVI,
                                     started_at=RUN.started_at, order_progress_pct=46.2),
                downtime=None, output_today=220, output_unit="m"),
    MachineCard(code="LOOM-05", name="Loom 5", stage="weaving", status="down", current_run=None,
                downtime=DowntimeOut(reason="Warp beam broken", started_at=NOW - dt.timedelta(minutes=40)),
                output_today=90, output_unit="m"),
    MachineCard(code="DYE-01", name="Jigger 1", stage="dyeing", status="running",
                current_run=RunBrief(id=46, order_code="ORD-0012", stage="dyeing", operator=Ref(id=6, name="Suresh"),
                                     started_at=NOW - dt.timedelta(hours=1), order_progress_pct=30.8),
                downtime=None, output_today=330, output_unit="m"),
]
BOARD = FloorBoard(machines=CARDS, running=2, idle=1, down=1, generated_at=NOW)
DETAIL = MachineDetail(**CARDS[1].model_dump(), recent_runs=[RUN])
ROLL = RollOut(id=142, code="R-0142", order_code="ORD-0012", buyer_name="Sharma Fabrics", fabric="Poplin 58in",
               colour="navy", metres=110, status="woven", created_at=NOW - dt.timedelta(hours=1))
