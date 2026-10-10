from app.core.schemas import Out


class CostParts(Out):
    yarn: float
    machine: float
    labour: float
    rework: float


class RollCost(Out):
    roll_code: str
    parts: CostParts
    reject_share: float
    total: float
    per_metre: float
    provisional: bool
