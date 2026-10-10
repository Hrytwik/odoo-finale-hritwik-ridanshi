"""The tool loop: ask the model, run the tools it asks for, give it the results, repeat (at most 6 times).

Identical for every provider. The model only chooses and words; every number it may use comes back from a tool, and
each tool call is kept as a source so the screen can show where an answer came from.
"""
import datetime as dt
import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.core.clock import today_ist
from app.core.errors import AppError
from app.modules.llm.data import ToolContext
from app.modules.llm.tools import Tool
from app.modules.llm.types import AdapterError, Completion, ToolResult, Turn
from app.modules.llm.adapters import LlmAdapter

MAX_STEPS = 6
RESULT_LIMIT = 6000
SUMMARY_LIMIT = 280

COPILOT_SYSTEM = (
    "You are the assistant for the owner and managers of Everest Textile Mills, a textile mill. "
    "Answer only from the results of the tools you call. Never calculate, estimate or guess a number: copy numbers exactly as the tools give them. "
    "If the tools do not give the answer, say you do not have that information. "
    "Money is in Indian rupees. Dates are in India time. Keep answers short, plain and specific."
)
BUYER_SYSTEM = (
    "You help a buyer of Everest Textile Mills with their own orders. "
    "Answer only from the results of the tools you call, and never calculate, estimate or guess a number or a date. "
    "If the tools do not show it, say you do not know and suggest they ring the mill. "
    "Never mention costs, margins, prices of yarn, machines, workers or other buyers. Be brief and polite."
)


@dataclass
class Source:
    tool: str
    input: dict
    summary: str


@dataclass
class ChatResult:
    text: str
    sources: list[Source] = field(default_factory=list)


def _summary(content: str) -> str:
    return content if len(content) <= SUMMARY_LIMIT else content[: SUMMARY_LIMIT - 1] + "…"


def with_today(system: str, today: dt.date | None = None) -> str:
    """Tells the model the date in India, so "this month" and "last week" mean something."""
    day = today or today_ist()
    return f"{system} Today is {day.isoformat()} (India time), so this month is {day:%Y-%m}."


def run_chat(adapter: LlmAdapter, system: str, history: list[Turn], question: str, tools: list[Tool], ctx: ToolContext,
             options: dict | None = None) -> ChatResult:
    """Answers one question. Raises AppError AI_UNAVAILABLE when the provider cannot be used."""
    system = with_today(system)
    by_name = {t.name: t for t in tools}
    specs = [t.spec() for t in tools]
    turns = [*history, Turn(role="user", text=question)]
    sources: list[Source] = []
    for _ in range(MAX_STEPS):
        completion = _complete(adapter, system, turns, specs, options)
        if not completion.tool_calls:
            return ChatResult(text=completion.text or "I could not find an answer.", sources=sources)
        turns.append(Turn(role="assistant", text=completion.text, tool_calls=completion.tool_calls))
        results = [_run_tool(call, by_name, ctx, sources) for call in completion.tool_calls]
        turns.append(Turn(role="tool", tool_results=results))
    return ChatResult(text="I could not finish looking that up. Please ask a narrower question.", sources=sources)


def _complete(adapter: LlmAdapter, system: str, turns: list[Turn], specs, options) -> Completion:
    try:
        try:
            return adapter.complete(system, turns, specs, options)
        except AdapterError as exc:
            if exc.kind != "bad_request":
                raise
            # some models now and then write a tool call the provider rejects; the same request usually works again
            return adapter.complete(system, turns, specs, options)
    except AdapterError as exc:
        raise ai_unavailable(exc) from exc


def ai_unavailable(exc: AdapterError | None = None) -> AppError:
    detail = f" ({exc.message})" if exc else ""
    return AppError("AI_UNAVAILABLE", f"AI unavailable. Check Settings or the connection{detail}", status=503)


def _run_tool(call, by_name: dict[str, Tool], ctx: ToolContext, sources: list[Source]) -> ToolResult:
    tool = by_name.get(call.name)
    if tool is None:
        # not in this role's list: refused, whatever the model asked for
        sources.append(Source(call.name, call.arguments, "Not available"))
        return ToolResult(call.id, call.name, "That tool is not available.", is_error=True)
    try:
        args = tool.input_model.model_validate(call.arguments)
    except ValidationError as exc:
        message = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        sources.append(Source(call.name, call.arguments, _summary(f"Bad input: {message}")))
        return ToolResult(call.id, call.name, f"Invalid input: {message}", is_error=True)
    try:
        content = json.dumps(tool.run(ctx, args), default=str, ensure_ascii=False)
    except AppError as exc:
        sources.append(Source(call.name, args.model_dump(), _summary(exc.message)))
        return ToolResult(call.id, call.name, exc.message, is_error=True)
    sources.append(Source(call.name, args.model_dump(), _summary(content)))
    return ToolResult(call.id, call.name, content[:RESULT_LIMIT])
