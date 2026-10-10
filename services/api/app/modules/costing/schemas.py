from typing import Literal

from app.core.enums import Stage
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

class OrderCost(Out):
    order_code: str
    parts: CostParts
    reject_cost: float
    total: float
    good_metres: float
    rejected_metres: float
    cost_per_good_metre: float | None
    revenue: float
    profit: float
    unabsorbed: float
    provisional: bool
    warnings: list[str]


class ProfitPanel(Out):
    invoiced: float
    yarn_issued: float
    wages_earned: float
    idle_labour: float
    machine_running_cost: float
    stock_writeoffs: float
    profit: float


class CashPanel(Out):
    received_from_buyers: float
    paid_to_suppliers: float
    paid_wages: float
    net_cash: float
    receivables_outstanding: float
    payables_outstanding: float


class MachineMonth(Out):
    code: str
    name: str
    stage: Stage
    running_h: float
    idle_h: float
    down_h: float
    output: float
    output_unit: Literal["kg", "m"]
    lost_capacity: float
    lost_capacity_unit: Literal["kg", "m"]


class OrderMonth(Out):
    order_code: str
    buyer_name: str
    revenue: float
    cost: float
    profit: float


class MonthReport(Out):
    month: str
    profit: ProfitPanel
    cash: CashPanel
    machines: list[MachineMonth]
    orders: list[OrderMonth]
    warnings: list[str]
