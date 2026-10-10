import datetime as dt
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.core.schemas import Out

Provider = Literal["anthropic", "openai_compatible"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class SettingsOut(Out):
    provider: Provider
    model: str
    base_url: str | None
    supports_tools: bool
    supports_vision: bool
    # the key itself is never returned, only whether one is stored
    api_key_set: bool
    configured: bool


class ModelsOut(BaseModel):
    """The model names the saved provider says this key can use."""
    models: list[str]


class SettingsIn(BaseModel):
    provider: Provider
    model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    base_url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    # None keeps the stored key; an empty string removes it
    api_key: Annotated[str, StringConstraints(max_length=500)] | None = None
    supports_tools: bool = True
    supports_vision: bool = False

    @field_validator("base_url")
    @classmethod
    def check_url(cls, url: str | None) -> str | None:
        if url:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("The address must start with http:// or https://")
        return url or None


class ChatTurnIn(BaseModel):
    role: Literal["user", "assistant"]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ChatIn(BaseModel):
    question: Text
    history: Annotated[list[ChatTurnIn], Field(max_length=12)] = []


class SourceOut(BaseModel):
    tool: str
    input: dict
    summary: str


class ChatOut(BaseModel):
    answer: str
    sources: list[SourceOut]
    provider: str
    model: str


class MonthIn(BaseModel):
    month: Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


class DraftOut(BaseModel):
    text: str
    sources: list[SourceOut]
    provider: str
    model: str


class RecallDraft(BaseModel):
    buyer_name: str
    message: str


class RecallDraftsOut(BaseModel):
    drafts: list[RecallDraft]
    sources: list[SourceOut]
    provider: str
    model: str


class EvalDetail(BaseModel):
    question: str
    expected: str
    answer: str
    passed: bool


class ReportCardOut(Out):
    id: int
    provider: str
    model: str
    run_at: dt.datetime
    score: int
    total: int
    details: list[EvalDetail]
