"""The fixed, read-only functions the model may call. It chooses which to call and with what; we run them and hand back
the results. No tool writes to the database, none takes a buyer id, and none runs model-written SQL."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.modules.llm import data
from app.modules.llm.data import ToolContext
from app.modules.llm.types import ToolSpec

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Month = Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
MANAGERS = frozenset({"owner", "accountant", "supervisor"})
FINANCE = frozenset({"owner", "accountant"})
BUYERS = frozenset({"buyer"})


class NoInput(BaseModel):
    pass


class OrderIn(BaseModel):
    order_code: Code


class MonthIn(BaseModel):
    month: Month


class StateIn(BaseModel):
    state: str = Field("", description="Leave empty for all, or one state such as confirmed, draft, cancelled, loading or dispatched.")


class LotIn(BaseModel):
    lot_code: Code


class RollIn(BaseModel):
    roll_code: Code


class MachineIn(BaseModel):
    machine_code: Code


class RollsIn(BaseModel):
    status: str = Field("", description="Leave empty for all, or one roll status such as awaiting_qc, in_store, loading, dispatched, rejected.")
    order_code: str = Field("", description="Leave empty for all, or an order code like ORD-0001.")


class BlockedIn(BaseModel):
    blocked: bool = Field(False, description="true to list only blocked lots, false for every lot.")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    roles: frozenset[str]
    feature: Literal["copilot", "buyer"]
    run: Callable[[ToolContext, BaseModel], object]

    def spec(self) -> ToolSpec:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        return ToolSpec(name=self.name, description=self.description, schema=schema)


TOOLS: tuple[Tool, ...] = (
    Tool("get_order_status", "Stage, progress, deadline, yarn status and delivery date of one order, by its code like ORD-0012.",
         OrderIn, MANAGERS, "copilot", lambda c, a: data.order_status(c, a.order_code)),
    Tool("get_order_cost", "What one order cost (yarn, labour, machine, rework), its revenue, profit and cost per good metre.",
         OrderIn, FINANCE, "copilot", lambda c, a: data.order_cost(c, a.order_code)),
    Tool("get_month_summary", "Profit, cash, orders and warnings for one month (YYYY-MM).",
         MonthIn, FINANCE, "copilot", lambda c, a: data.month_summary(c, a.month)),
    Tool("get_machine_utilisation", "Running, idle and down hours per machine for one month (YYYY-MM), with lost capacity.",
         MonthIn, FINANCE, "copilot", lambda c, a: data.machine_utilisation(c, a.month)),
    Tool("get_late_orders", "Orders that will miss their deadline, with the bottleneck stage and what would fix them.",
         NoInput, MANAGERS, "copilot", lambda c, a: data.late_orders(c)),
    Tool("get_shortage_forecast", "Yarn types that are or will be below their reorder level, with the supplier and how much to order.",
         NoInput, MANAGERS, "copilot", lambda c, a: data.shortages(c)),
    Tool("get_defect_root_causes", "Which machines, operators, shifts or yarn lots have a defect rate unlikely to be chance.",
         NoInput, MANAGERS, "copilot", lambda c, a: data.root_causes(c)),
    Tool("get_stock", "Yarn stock per type: on hand, needed by open orders, free, and the reorder level.",
         NoInput, MANAGERS, "copilot", lambda c, a: data.stock(c)),
    Tool("list_orders", "Every order in one line: buyer, fabric, colour, metres, deadline, state, stage, yarn status and metres woven, dyed, passed and dispatched. Use for 'which orders', 'how many orders' or any question about orders in general.",
         StateIn, MANAGERS, "copilot", lambda c, a: data.orders_overview(c, a.state)),
    Tool("list_fabric_types", "The fabric types the mill makes, with width, wastage and the yarn recipe (kg of each yarn per metre).",
         NoInput, MANAGERS, "copilot", lambda c, a: data.fabric_types(c)),
    Tool("list_yarn_types", "The yarn types: code, name, colour and reorder level.",
         NoInput, MANAGERS, "copilot", lambda c, a: data.yarn_types(c)),
    Tool("list_machines", "Every machine: code, name, stage (spinning, weaving, dyeing), speed, running cost and whether it is active.",
         NoInput, MANAGERS, "copilot", lambda c, a: data.machines(c)),
    Tool("get_floor_board", "What every machine is doing right now: running (with its order and operator), idle or down.",
         NoInput, MANAGERS, "copilot", lambda c, a: data.floor_board(c)),
    Tool("get_machine", "One machine by code (like LOOM-04): its state now, current run and today's output.",
         MachineIn, MANAGERS, "copilot", lambda c, a: data.machine_detail(c, a.machine_code)),
    Tool("list_yarn_lots", "Yarn lots received: lot code, yarn, supplier, quantity, cost per kg, on hand, and whether blocked.",
         BlockedIn, MANAGERS, "copilot", lambda c, a: data.lots(c, True if a.blocked else None)),
    Tool("get_yarn_lot", "One yarn lot by code (like L-0001): its details and stock ledger.",
         LotIn, MANAGERS, "copilot", lambda c, a: data.lot_detail(c, a.lot_code)),
    Tool("list_rolls", "Fabric rolls with code, order, metres and status; filter by status or order.",
         RollsIn, MANAGERS, "copilot", lambda c, a: data.rolls_list(c, a.status, a.order_code)),
    Tool("get_roll_passport", "The full life of one roll by code (like R-0001): runs, yarn lots, quality checks and dispatch.",
         RollIn, MANAGERS, "copilot", lambda c, a: data.roll_passport(c, a.roll_code)),
    Tool("get_qc_queue", "Rolls waiting for a quality check or rework, and counts of passed, reworked and rejected rolls.",
         NoInput, MANAGERS, "copilot", lambda c, a: data.qc_queue(c)),
    Tool("list_dispatches", "Trucks: code, buyer, vehicle, state and what is loaded; filter by state (loading or dispatched).",
         StateIn, FINANCE, "copilot", lambda c, a: data.dispatches(c, a.state)),
    Tool("get_receivables", "Invoices and what each buyer still owes, with due dates and overdue flags.",
         NoInput, FINANCE, "copilot", lambda c, a: data.receivables(c)),
    Tool("get_payables", "Supplier bills and what the mill still owes each supplier, with due dates and overdue flags.",
         NoInput, FINANCE, "copilot", lambda c, a: data.payables(c)),
    Tool("get_wages", "Wages earned, paid and owed for each worker for one month (YYYY-MM).",
         MonthIn, FINANCE, "copilot", lambda c, a: data.wages(c, a.month)),
    Tool("list_buyers", "The buyers (customers) of the mill.",
         NoInput, FINANCE, "copilot", lambda c, a: data.buyers(c)),
    Tool("list_suppliers", "The yarn suppliers and their lead times.",
         NoInput, FINANCE, "copilot", lambda c, a: data.suppliers(c)),
    Tool("list_workers", "The workers on the payroll with role and daily wage.",
         NoInput, FINANCE, "copilot", lambda c, a: data.workers(c)),
    Tool("get_my_orders", "The logged-in buyer's own orders with stage, progress and dates.",
         NoInput, BUYERS, "buyer", lambda c, a: data.my_orders(c)),
    Tool("get_my_order_status", "One of the logged-in buyer's own orders by code: stage, progress, timeline and dispatches.",
         OrderIn, BUYERS, "buyer", lambda c, a: data.my_order(c, a.order_code)),
    Tool("get_my_order_eta", "The promised deadline and the expected delivery date of one of the logged-in buyer's own orders.",
         OrderIn, BUYERS, "buyer", lambda c, a: _eta(data.my_order(c, a.order_code))),
)
BY_NAME = {t.name: t for t in TOOLS}


def _eta(order: dict) -> dict:
    return {"code": order.get("code"), "deadline": order.get("deadline"), "delivery_date": order.get("delivery_date"),
            "stage": order.get("stage")}


def tools_for(role: str, feature: Literal["copilot", "buyer"]) -> list[Tool]:
    """The tools this role may be offered for this feature. A tool outside the list cannot be called even if the model asks."""
    return [t for t in TOOLS if t.feature == feature and role in t.roles]
