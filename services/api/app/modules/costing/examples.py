from app.modules.costing.schemas import (
    CashPanel, CostParts, MachineMonth, MonthReport, OrderCost, OrderMonth, ProfitPanel,
)
from app.modules.passport.examples import PASSPORT

ROLL_COST = PASSPORT.cost
ORDER_COST = OrderCost(
    order_code="ORD-0012", parts=CostParts(yarn=146875, machine=52300, labour=28800, rework=18400),
    reject_cost=13600, total=246375, good_metres=1210, rejected_metres=110, cost_per_good_metre=203.6,
    revenue=145200, profit=-101175, unabsorbed=0, provisional=True, warnings=[],
)
MONTH = MonthReport(
    month="2026-10",
    profit=ProfitPanel(invoiced=412000, yarn_issued=198500, wages_earned=96000, idle_labour=14200,
                       machine_running_cost=61500, stock_writeoffs=2500, profit=53500),
    cash=CashPanel(received_from_buyers=260000, paid_to_suppliers=150000, paid_wages=80000, net_cash=30000,
                   receivables_outstanding=152000, payables_outstanding=248500),
    machines=[MachineMonth(code="LOOM-04", name="Loom 4", stage="weaving", running_h=180, idle_h=31, down_h=12,
                           output=3960, output_unit="m", lost_capacity=946, lost_capacity_unit="m")],
    orders=[OrderMonth(order_code="ORD-0012", buyer_name="Sharma Fabrics", revenue=145200, cost=246375,
                       profit=-101175)],
    warnings=["Run 52 (Loom 5, 2026-10-08) has no attendance for its operator"],
)
