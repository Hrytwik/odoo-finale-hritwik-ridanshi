import datetime as dt

from app.core.enums import Verdict
from app.core.schemas import Out
from app.modules.qc.schemas import AiSuggestion, DefectOut


class LogItem(Out):
    id: int
    roll_code: str
    order_code: str
    buyer_name: str
    fabric: str
    colour: str
    metres: float
    lots: list[str]  # the yarn lots (batches) the roll was woven from
    inspector: str
    inspected_at: dt.datetime
    verdict: Verdict
    overrode_ai: bool
    defects: list[DefectOut]
    remark: str | None
    photo_url: str | None
    ai: AiSuggestion | None


class LogCounts(Out):
    total: int
    passed: int
    rework: int
    rejected: int
    overrode_ai: int


class LogPage(Out):
    items: list[LogItem]
    counts: LogCounts
    limit: int
    offset: int


class OrderOption(Out):
    code: str
    buyer_name: str


class LogFilters(Out):
    orders: list[OrderOption]
    lots: list[str]
