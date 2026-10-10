"""The only place the language-model module reads the mill's numbers from.

Each function asks one of the other modules' own endpoint functions, so the roles, the buyer scoping and the real
calculations stay where they are written; this module never calculates a number. When a module changes how it gets its
data, only this file needs to follow.
"""
import inspect
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import User
from app.modules.costing import router as costing
from app.modules.insights import router as insights
from app.modules.orders import router as orders
from app.modules.portal import router as portal
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
