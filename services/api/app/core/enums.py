from typing import Literal

Stage = Literal["spinning", "weaving", "dyeing"]
RunStage = Literal["spinning", "weaving", "dyeing", "rework"]
MachineStatus = Literal["running", "idle", "down"]
RollStatus = Literal[
    "woven", "dyeing", "awaiting_qc", "awaiting_rework", "in_rework",
    "in_store", "rejected", "loading", "dispatched",
]
OrderState = Literal["draft", "confirmed", "cancelled"]
OrderStage = Literal[
    "draft", "cancelled", "waiting_to_start", "spinning", "weaving", "dyeing",
    "quality_check", "ready_to_ship", "partly_dispatched", "dispatched", "closed_short",
]
Verdict = Literal["pass", "rework", "reject"]
DefectType = Literal["hole", "stain", "thread_fault", "colour_mismatch", "other"]
Role = Literal["owner", "accountant", "store", "supervisor", "qc", "dispatch", "buyer"]
WorkerRole = Literal["operator", "inspector", "storekeeper", "supervisor", "dispatch", "helper"]
DispatchState = Literal["loading", "dispatched"]
MovementKind = Literal["receipt", "issue", "return", "adjustment"]
RollRunPurpose = Literal["produce", "dye", "rework"]
AttendanceStatus = Literal["present", "half_day", "absent"]
