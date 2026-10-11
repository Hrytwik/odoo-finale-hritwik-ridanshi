import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.errors import AppError, commit
from app.db.models import LlmEvalRun, LlmSettings, User
from app.db.session import get_db
from app.modules.llm import crypto, data, engine, reportcard
from app.modules.llm import schemas as s
from app.modules.llm.data import ToolContext
from app.modules.llm.runtime import LlmConfig, LlmRuntime, get_runtime, load_config
from app.modules.llm.tools import tools_for
from app.modules.llm.types import AdapterError, Turn

router = APIRouter(prefix="/ai", tags=["ai"])
owner_only = require_roles("owner")
managers = require_roles("owner", "accountant", "supervisor")
finance = require_roles("owner", "accountant")
buyers = require_roles("buyer")
recall_readers = require_roles("owner", "store")


def _out(cfg: LlmConfig) -> s.SettingsOut:
    return s.SettingsOut(provider=cfg.provider, model=cfg.model, base_url=cfg.base_url, supports_tools=cfg.supports_tools,
                         supports_vision=cfg.supports_vision, api_key_set=bool(cfg.api_key), configured=cfg.configured)


@router.get("/settings", response_model=s.SettingsOut, dependencies=[Depends(owner_only)])
def get_settings(db: Session = Depends(get_db)) -> s.SettingsOut:
    return _out(load_config(db))


@router.put("/settings", response_model=s.SettingsOut)
def put_settings(body: s.SettingsIn, db: Session = Depends(get_db), user: User = Depends(owner_only)) -> s.SettingsOut:
    """Saves the provider, model and address. The key is encrypted before it is stored and is never sent back."""
    if body.provider == "openai_compatible" and not body.base_url:
        raise AppError("VALIDATION_ERROR", "An OpenAI-compatible provider needs an address", field="base_url", status=422)
    row = db.get(LlmSettings, 1)
    if row is None:
        row = LlmSettings(id=1, provider=body.provider, model=body.model, supports_tools=True, supports_vision=False)
        db.add(row)
    row.provider, row.model = body.provider, body.model
    row.base_url = body.base_url or None
    row.supports_tools, row.supports_vision = body.supports_tools, body.supports_vision
    row.updated_by = user.id
    if body.api_key is not None:
        row.api_key_encrypted = crypto.encrypt_key(body.api_key) if body.api_key.strip() else None
    commit(db)
    return _out(load_config(db))


@router.get("/models", response_model=s.ModelsOut, dependencies=[Depends(owner_only)])
def list_models(rt: LlmRuntime = Depends(get_runtime)) -> s.ModelsOut:
    """Asks the saved provider which models this key may use, so the owner picks a name that exists."""
    try:
        return s.ModelsOut(models=rt.adapter.models())
    except AdapterError as exc:
        raise engine.ai_unavailable(exc) from exc


def _sources(result: engine.ChatResult) -> list[s.SourceOut]:
    return [s.SourceOut(tool=x.tool, input=x.input, summary=x.summary) for x in result.sources]


def _need_tools(rt: LlmRuntime) -> None:
    if not rt.config.supports_tools:
        raise AppError("AI_NO_TOOLS", "The selected model cannot call tools, so the assistant is turned off. Choose another model in Settings.", status=409)


def _history(body: s.ChatIn) -> list[Turn]:
    return [Turn(role=t.role, text=t.text) for t in body.history]


@router.post("/copilot", response_model=s.ChatOut)
def copilot(body: s.ChatIn, db: Session = Depends(get_db), user: User = Depends(managers), rt: LlmRuntime = Depends(get_runtime)) -> s.ChatOut:
    _need_tools(rt)
    result = engine.run_chat(rt.adapter, engine.COPILOT_SYSTEM, _history(body), body.question, tools_for(user.role, "copilot"), ToolContext(db, user),
                             language=body.language)
    return s.ChatOut(answer=result.text, sources=_sources(result), provider=rt.config.provider, model=rt.config.model)


@router.post("/buyer-assistant", response_model=s.ChatOut)
def buyer_assistant(body: s.ChatIn, db: Session = Depends(get_db), user: User = Depends(buyers), rt: LlmRuntime = Depends(get_runtime)) -> s.ChatOut:
    _need_tools(rt)
    result = engine.run_chat(rt.adapter, engine.BUYER_SYSTEM, _history(body), body.question, tools_for(user.role, "buyer"), ToolContext(db, user),
                             language=body.language)
    return s.ChatOut(answer=result.text, sources=_sources(result), provider=rt.config.provider, model=rt.config.model)


def _write(rt: LlmRuntime, system: str, prompt: str, language: str | None = None) -> str:
    """One plain model call with no tools: the model only words figures we hand it."""
    reply = None
    try:
        for budget in (700, 1500):  # a model that thinks first may need more room; a draft is never handed back cut off
            reply = rt.adapter.complete(engine.with_language(system, language), [Turn(role="user", text=prompt)], [], {"max_tokens": budget})
            if not reply.truncated:
                break
    except AdapterError as exc:
        raise engine.ai_unavailable(exc) from exc
    text = (reply.text if reply else "") or ""
    return text + " ..." if reply and reply.truncated and text else text


def _source(tool: str, input: dict, payload: object) -> s.SourceOut:
    return s.SourceOut(tool=tool, input=input, summary=engine._summary(json.dumps(payload, default=str, ensure_ascii=False)))


@router.post("/explain-delay/{order_code}", response_model=s.DraftOut)
def explain_delay(order_code: str, db: Session = Depends(get_db), user: User = Depends(managers), rt: LlmRuntime = Depends(get_runtime)) -> s.DraftOut:
    """Words the delivery estimate and the two tested what-ifs. It cannot propose a fix that the code did not test."""
    eta = data.order_eta(ToolContext(db, user), order_code)
    text = _write(
        rt,
        "You explain a delivery estimate to a mill manager in two or three plain sentences. Use only the figures given. "
        "Mention only the what-ifs listed, with their dates. Do not suggest anything else and do not invent causes.",
        json.dumps(eta, default=str),
    )
    return s.DraftOut(text=text, sources=[_source("get_order_eta", {"order_code": order_code}, eta)], provider=rt.config.provider, model=rt.config.model)


@router.post("/recall-drafts/{lot_code}", response_model=s.RecallDraftsOut)
def recall_drafts(lot_code: str, db: Session = Depends(get_db), user: User = Depends(recall_readers), rt: LlmRuntime = Depends(get_runtime)) -> s.RecallDraftsOut:
    """A short message for each buyer who received rolls made from this yarn lot. A person reads and sends them."""
    recall = data.lot_recall(ToolContext(db, user), lot_code)
    drafts = []
    for b in recall["buyers"][:10]:
        message = _write(
            rt,
            "You draft a short, calm message from Everest Textile Mills to a buyer about a yarn lot that has been blocked. "
            "Use only the facts given, do not state a cause, and ask them to hold the listed rolls until the mill contacts them.",
            json.dumps({"lot_code": lot_code, **b}, default=str),
        )
        drafts.append(s.RecallDraft(buyer_name=b["buyer_name"], message=message))
    return s.RecallDraftsOut(drafts=drafts, sources=[_source("get_lot_recall", {"lot_code": lot_code}, recall)],
                             provider=rt.config.provider, model=rt.config.model)


@router.post("/month-summary", response_model=s.DraftOut)
def month_summary(body: s.MonthIn, db: Session = Depends(get_db), user: User = Depends(finance), rt: LlmRuntime = Depends(get_runtime)) -> s.DraftOut:
    report = data.month_summary(ToolContext(db, user), body.month)
    text = _write(
        rt,
        "You write one paragraph of four to six sentences summarising a mill's month for its owner. Use only the numbers given, "
        "copied exactly, in Indian rupees. Mention profit, cash, and anything in the warnings. Do not give advice.",
        json.dumps(report, default=str),
        body.language,
    )
    return s.DraftOut(text=text, sources=[_source("get_month_summary", {"month": body.month}, report)], provider=rt.config.provider, model=rt.config.model)


@router.post("/report-card/run", response_model=s.ReportCardOut, status_code=201)
def run_report_card(db: Session = Depends(get_db), user: User = Depends(owner_only), rt: LlmRuntime = Depends(get_runtime)) -> s.ReportCardOut:
    """Asks the model the questions in `reportcard` and marks each answer against the figure read from the data just now."""
    _need_tools(rt)
    ctx = ToolContext(db, user)
    tools = tools_for(user.role, "copilot")
    details: list[s.EvalDetail] = []
    for q in reportcard.build_questions(ctx):
        answer = engine.run_chat(rt.adapter, engine.COPILOT_SYSTEM, [], q.text, tools, ctx).text
        details.append(s.EvalDetail(question=q.text, expected=q.expected(), answer=answer, passed=reportcard.passes(q, answer)))
    if not details:
        raise AppError("NO_DATA", "There is no data to ask questions about yet", status=409)
    run = LlmEvalRun(provider=rt.config.provider, model=rt.config.model, score=sum(d.passed for d in details),
                     total=len(details), details=[d.model_dump() for d in details])
    db.add(run)
    commit(db)
    db.refresh(run)
    return s.ReportCardOut.model_validate(run)


@router.get("/report-card", response_model=list[s.ReportCardOut], dependencies=[Depends(owner_only)])
def report_cards(db: Session = Depends(get_db)) -> list[s.ReportCardOut]:
    """The most recent runs, newest first, so two models can be compared."""
    runs = db.scalars(select(LlmEvalRun).order_by(LlmEvalRun.run_at.desc(), LlmEvalRun.id.desc()).limit(10))
    return [s.ReportCardOut.model_validate(r) for r in runs]
