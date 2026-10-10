"""The fixed, read-only functions the model may call. It chooses which to call and with what; we run them and hand back
the results. No tool writes to the database, none takes a buyer id, and none runs model-written SQL."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

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
