"""The report card: questions about the mill's current data whose right answers are read from the data at run time,
so they stay correct as the data changes. An answer passes when it contains the expected value."""
import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.modules.llm import data
from app.modules.llm.data import ToolContext

NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass
class Question:
    text: str
    numbers: list[float] = field(default_factory=list)       # every one of these must appear
    any_numbers: list[float] = field(default_factory=list)   # at least one of these must appear
    words: list[str] = field(default_factory=list)           # every one of these must appear as a word
    any_words: list[str] = field(default_factory=list)       # at least one of these must appear

    def expected(self) -> str:
        parts = [*(f"{n:g}" for n in self.numbers), *self.words]
        if self.any_numbers:
            parts.append(" or ".join(f"{n:g}" for n in self.any_numbers))
        if self.any_words:
            parts.append(" or ".join(self.any_words))
        return "; ".join(parts)


def numbers_in(text: str) -> list[float]:
    """Numbers in an answer, with grouping commas and rupee signs ignored: '₹1,98,500.50' reads as 198500.5."""
    cleaned = re.sub(r"(?<=\d),(?=\d)", "", text.replace("₹", " "))
    return [float(m) for m in NUMBER.findall(cleaned)]


def _has_number(found: list[float], wanted: float) -> bool:
    return any(abs(f - wanted) <= max(0.005, abs(wanted) * 1e-9) for f in found)


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word.lower())}\b", text.lower()) is not None


def passes(q: Question, answer: str) -> bool:
    found = numbers_in(answer)
    return (
        all(_has_number(found, n) for n in q.numbers)
        and (not q.any_numbers or any(_has_number(found, n) for n in q.any_numbers))
        and all(_has_word(answer, w) for w in q.words)
        and (not q.any_words or any(_has_word(answer, w) for w in q.any_words))
    )


def _stage_words(stage: str) -> list[str]:
    return stage.replace("_", " ").split()


def build_questions(ctx: ToolContext, today: dt.date | None = None) -> list[Question]:
    """Up to 15 questions, each from whatever data exists right now; one with no data behind it is left out."""
    month = (today or dt.date.today()).strftime("%Y-%m")
    questions: list[Question] = []

    def add(make: Callable[[], Question | None]) -> None:
        try:
            q = make()
        except Exception:  # noqa: BLE001  (a missing or broken data source just leaves its question out)
            return
        if q:
            questions.append(q)

    def fetch(get: Callable[[], object], fallback: object) -> object:
        try:
            return get()
        except Exception:  # noqa: BLE001  (a source that fails leaves its questions out; the rest still run)
            return fallback

    stock = fetch(lambda: data.stock(ctx), [])
    orders = fetch(lambda: data.orders_list(ctx), [])
    late = fetch(lambda: data.late_orders(ctx), [])
    shortages = fetch(lambda: data.shortages(ctx), [])
    causes = fetch(lambda: data.root_causes(ctx), [])
    report = fetch(lambda: data.month_summary(ctx, month), None)
    y = stock[0] if stock else None
    name = (lambda r: f"{r['yarn_type']['name']} ({r['yarn_type']['colour']})")

    add(lambda: y and Question(f"How many kg of {name(y)} are free right now?", numbers=[y["free_kg"]]))
    add(lambda: y and Question(f"How many kg of {name(y)} are on hand?", numbers=[y["on_hand_kg"]]))
    add(lambda: y and Question(f"What is the reorder level of {name(y)} in kg?", numbers=[y["reorder_level_kg"]]))
    add(lambda: y and Question(f"Is {name(y)} below its reorder level? Answer yes or no.", any_words=["yes"] if y["below_reorder"] else ["no"]))
    add(lambda: Question("How many orders are late?", numbers=[float(len(late))]))
    add(lambda: orders and Question(f"What stage is order {orders[0]['code']} in?", any_words=_stage_words(orders[0]["stage"])))
    add(lambda: orders and Question(f"What is the deadline of order {orders[0]['code']}?", any_words=_date_forms(orders[0]["deadline"])))
    add(lambda: late and Question(f"How many days late is order {late[0]['order_code']}?", numbers=[float(late[0]["days_late"])]))
    add(lambda: late and late[0]["bottleneck_stage"] and Question(f"Which stage is holding up order {late[0]['order_code']}?", words=[late[0]["bottleneck_stage"]]))
    add(lambda: report and Question(f"What was the net profit for {month}?", numbers=[report["profit"]["profit"]]))
    add(lambda: report and Question(f"How much money did we receive from buyers in {month}?", numbers=[report["cash"]["received_from_buyers"]]))
    add(lambda: report and report["machines"] and Question(f"How many hours was {report['machines'][0]['name']} down in {month}?", numbers=[report["machines"][0]["down_h"]]))
    add(lambda: causes and Question(f"What is the defect rate of {causes[0]['value']}, as a percentage?", any_numbers=[round(causes[0]["rate"] * 100, 2), causes[0]["rate"]]))
    add(lambda: shortages and Question(f"How many kg of {shortages[0]['yarn_type']['name']} should we order?", numbers=[shortages[0]["suggested_kg"]]))
    add(lambda: Question("How many orders do we have in total?", numbers=[float(len(orders))]))
    return questions


_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _date_forms(iso: str) -> list[str]:
    """The ways an answer may write a date: 2026-10-20, 20 Oct, 20 October."""
    y, m, d = (int(p) for p in iso.split("-"))
    short = _MONTHS[m - 1]
    full = dt.date(y, m, d).strftime("%B").lower()
    return [iso, f"{d} {short}", f"{d} {full}", f"{short} {d}", f"{full} {d}"]
