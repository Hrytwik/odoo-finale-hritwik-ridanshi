"""Our own neutral message and tool formats. Each provider adapter translates to and from these."""
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class Turn:
    """One message in the conversation. Assistant turns may carry tool calls; tool turns carry their results."""
    role: Literal["user", "assistant", "tool"]
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict


@dataclass
class Completion:
    text: str
    tool_calls: list[ToolCall]


class AdapterError(Exception):
    """The provider could not answer. `kind` says why, in terms the settings page can act on."""

    def __init__(self, kind: Literal["unreachable", "auth", "bad_request", "server", "rate_limit"], message: str,
                 retry_after: float | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retry_after = retry_after  # seconds the provider asked us to wait, when it said
