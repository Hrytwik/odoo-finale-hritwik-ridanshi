"""The only place the language-model module reads the mill's numbers from.

Each function asks one of the other modules' own endpoint functions, so the roles, the buyer scoping and the real
calculations stay where they are written; this module never calculates a number. When a module changes how it gets its
data, only this file needs to follow.
"""
import inspect
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Buyer, Machine, Supplier, User, Worker, YarnType
from app.modules.costing import router as costing
from app.modules.dispatch import router as dispatch
from app.modules.floor import router as floor
from app.modules.insights import router as insights
from app.modules.master import router as master
from app.modules.master import schemas as master_schemas
from app.modules.money import router as money
from app.modules.orders import router as orders
from app.modules.passport import router as passport
from app.modules.people import router as people
from app.modules.portal import router as portal
from app.modules.qc import router as qc
from app.modules.rolls import router as rolls
from app.modules.store import router as store


@dataclass
class ToolContext:
    db: Session
    user: User


def dump(value: Any) -> Any:
    """Plain JSON-ready data from whatever an endpoint function returned."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [dump(v) for v in value]
    return value


def _call(handler, ctx: ToolContext, **kwargs):
    """Calls an endpoint function directly, handing it the database session and the user if it asks for them."""
    params = inspect.signature(handler).parameters
    if "db" in params:
        kwargs["db"] = ctx.db
    if "user" in params:
        kwargs["user"] = ctx.user
    return dump(handler(**kwargs))


def orders_list(ctx: ToolContext) -> list[dict]:
    return _call(orders.list_orders, ctx)


def order_status(ctx: ToolContext, order_code: str) -> dict:
    return {"order": _call(orders.get_order, ctx, order_code=order_code),
            "yarn_check": _call(orders.yarn_check, ctx, order_code=order_code)}


def order_cost(ctx: ToolContext, order_code: str) -> dict:
    return _call(costing.order_cost, ctx, order_code=order_code)


def month_summary(ctx: ToolContext, month: str) -> dict:
    return _call(costing.month_report, ctx, month=month)


def machine_utilisation(ctx: ToolContext, month: str) -> list[dict]:
    """Running, idle and down hours per machine, and the share of its time each machine ran (from the month report)."""
    rows = []
    for m in month_summary(ctx, month)["machines"]:
        total = m["running_h"] + m["idle_h"] + m["down_h"]
        rows.append({**m, "total_h": total, "running_share": round(m["running_h"] / total, 4) if total else 0})
    return rows


def late_orders(ctx: ToolContext) -> list[dict]:
    return _call(insights.late_orders, ctx)


def order_eta(ctx: ToolContext, order_code: str) -> dict:
    return _call(insights.order_eta, ctx, order_code=order_code)


def shortages(ctx: ToolContext) -> list[dict]:
    return _call(insights.shortages, ctx)


def root_causes(ctx: ToolContext) -> list[dict]:
    return _call(insights.root_causes, ctx)


def stock(ctx: ToolContext) -> list[dict]:
    return _call(store.stock, ctx)


def lot_recall(ctx: ToolContext, lot_code: str) -> dict:
    return _call(store.lot_recall, ctx, lot_code=lot_code)


# ---- the buyer's own orders: the portal functions scope to the logged-in buyer, so no buyer id is ever passed in ----

def my_orders(ctx: ToolContext) -> list[dict]:
    return _call(portal.my_orders, ctx)


def my_order(ctx: ToolContext, order_code: str) -> dict:
    return _call(portal.my_order, ctx, order_code=order_code)


# ---- the rest of what the dashboards show: lists and look-ups, so a question about any screen can be answered ----

ROW_LIMIT = 40  # a list is cut here, so the model is never handed half a row, and is told how many there were


def capped(rows: list) -> dict:
    return {"count": len(rows), "shown": min(len(rows), ROW_LIMIT), "rows": rows[:ROW_LIMIT]}


def orders_overview(ctx: ToolContext, state: str = "") -> dict:
    """Every order in one line: who, what, how much, deadline, stage and yarn status."""
    rows = [{"code": o["code"], "buyer": o["buyer"]["name"], "fabric": o["fabric_type"]["name"], "colour": o["colour"],
             "qty_metres": o["qty_metres"], "deadline": o["deadline"], "state": o["state"], "stage": o["stage"],
             "yarn_status": o["yarn_status"], "woven_m": o["progress"]["woven_m"], "dyed_m": o["progress"]["dyed_m"],
             "passed_m": o["progress"]["passed_m"], "dispatched_m": o["progress"]["dispatched_m"]}
            for o in _call(orders.list_orders, ctx, state=state or None)]
    return capped(rows)


def fabric_types(ctx: ToolContext) -> dict:
    return capped(_call(master.list_fabric_types, ctx))


def _master_rows(ctx: ToolContext, model, out, order_by) -> dict:
    return capped([out.model_validate(r).model_dump(mode="json") for r in ctx.db.scalars(select(model).order_by(order_by))])


def yarn_types(ctx: ToolContext) -> dict:
    return _master_rows(ctx, YarnType, master_schemas.YarnTypeOut, YarnType.code)


def machines(ctx: ToolContext) -> dict:
    return _master_rows(ctx, Machine, master_schemas.MachineOut, Machine.code)


def suppliers(ctx: ToolContext) -> dict:
    return _master_rows(ctx, Supplier, master_schemas.SupplierOut, Supplier.name)


def buyers(ctx: ToolContext) -> dict:
    return _master_rows(ctx, Buyer, master_schemas.BuyerOut, Buyer.name)


def workers(ctx: ToolContext) -> dict:
    return _master_rows(ctx, Worker, master_schemas.WorkerOut, Worker.code)


def floor_board(ctx: ToolContext) -> dict:
    return _call(floor.floor_board, ctx)


def machine_detail(ctx: ToolContext, machine_code: str) -> dict:
    return _call(floor.machine_detail, ctx, machine_code=machine_code)


def lots(ctx: ToolContext, blocked: bool | None = None) -> dict:
    return capped(_call(store.list_lots, ctx, blocked=blocked))


def lot_detail(ctx: ToolContext, lot_code: str) -> dict:
    return _call(store.get_lot, ctx, lot_code=lot_code)


def rolls_list(ctx: ToolContext, status: str = "", order_code: str = "") -> dict:
    return capped(_call(rolls.list_rolls, ctx, status=status or None, order_code=order_code or None))


def roll_passport(ctx: ToolContext, roll_code: str) -> dict:
    return _call(passport.roll_passport, ctx, roll_code=roll_code)


def qc_queue(ctx: ToolContext) -> dict:
    return _call(qc.qc_queue, ctx)


def dispatches(ctx: ToolContext, state: str = "") -> dict:
    return capped(_call(dispatch.list_dispatches, ctx, state=state or None))


def receivables(ctx: ToolContext) -> dict:
    return capped(_call(money.receivables, ctx))


def payables(ctx: ToolContext) -> dict:
    return capped(_call(money.payables, ctx))


def wages(ctx: ToolContext, month: str) -> dict:
    sheet = _call(people.wages, ctx, month=month)
    return {**sheet, "rows": sheet["rows"][:ROW_LIMIT], "workers": len(sheet["rows"])}
