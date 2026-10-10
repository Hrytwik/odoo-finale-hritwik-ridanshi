"""Provider adapters: one interface, `complete(system, turns, tools, options) -> Completion`.

Both adapters speak plain HTTPS JSON through `post_json`, so there is no SDK to install and tests can swap the transport.
"""
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol

from app.modules.llm.types import AdapterError, Completion, ToolCall, ToolSpec, Turn

PostJson = Callable[[str, dict[str, str], dict, float], dict]
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def post_json(url: str, headers: dict[str, str], payload: dict, timeout: float = 60) -> dict:
    """POST JSON, return the JSON reply. Failures become AdapterError; the key and the request are never put in a message."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https or the owner's own base URL)
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = _error_detail(exc)
        if exc.code in (401, 403):
            raise AdapterError("auth", "The provider refused the API key") from exc
        if exc.code >= 500:
            raise AdapterError("server", f"The provider had a problem ({exc.code})") from exc
        raise AdapterError("bad_request", detail or f"The provider refused the request ({exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AdapterError("unreachable", "Could not reach the provider") from exc
    except ValueError as exc:
        raise AdapterError("server", "The provider sent something unreadable") from exc


def _error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode())
        err = body.get("error")
        message = err.get("message") if isinstance(err, dict) else err
        return str(message)[:200] if message else ""
    except (ValueError, AttributeError, OSError):
        return ""


class LlmAdapter(Protocol):
    def complete(self, system: str, turns: list[Turn], tools: list[ToolSpec], options: dict | None = None) -> Completion: ...


class AnthropicAdapter:
    def __init__(self, api_key: str, model: str, post: PostJson = post_json, url: str = ANTHROPIC_URL):
        self.api_key, self.model, self.post, self.url = api_key, model, post, url

    @staticmethod
    def _messages(turns: list[Turn]) -> list[dict]:
        out: list[dict] = []
        for t in turns:
            if t.role == "user":
                out.append({"role": "user", "content": t.text})
            elif t.role == "assistant":
                blocks: list[dict] = [{"type": "text", "text": t.text}] if t.text else []
                blocks += [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in t.tool_calls]
                out.append({"role": "assistant", "content": blocks})
            else:
                out.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
                    for r in t.tool_results]})
        return out

    def complete(self, system: str, turns: list[Turn], tools: list[ToolSpec], options: dict | None = None) -> Completion:
        options = options or {}
        payload: dict = {"model": self.model, "max_tokens": options.get("max_tokens", 1024), "system": system,
                         "messages": self._messages(turns)}
        if tools:
            payload["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.schema} for t in tools]
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        data = self.post(self.url, {"x-api-key": self.api_key, "anthropic-version": ANTHROPIC_VERSION}, payload, 60)
        text, calls = "", []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                calls.append(ToolCall(id=block["id"], name=block["name"], arguments=block.get("input") or {}))
        return Completion(text=text.strip(), tool_calls=calls)


class OpenAICompatibleAdapter:
    """OpenAI, Groq, OpenRouter, or a local model through Ollama or LM Studio: anything that serves /chat/completions."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None, post: PostJson = post_json):
        self.base_url, self.model, self.api_key, self.post = base_url.rstrip("/"), model, api_key, post

    @staticmethod
    def _messages(system: str, turns: list[Turn]) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for t in turns:
            if t.role == "user":
                out.append({"role": "user", "content": t.text})
            elif t.role == "assistant":
                msg: dict = {"role": "assistant", "content": t.text or None}
                if t.tool_calls:
                    msg["tool_calls"] = [{"id": c.id, "type": "function",
                                          "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                                         for c in t.tool_calls]
                out.append(msg)
            else:
                out += [{"role": "tool", "tool_call_id": r.call_id, "content": r.content} for r in t.tool_results]
        return out

    def complete(self, system: str, turns: list[Turn], tools: list[ToolSpec], options: dict | None = None) -> Completion:
        options = options or {}
        payload: dict = {"model": self.model, "messages": self._messages(system, turns),
                         "max_tokens": options.get("max_tokens", 1024)}
        if tools:
            payload["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                                   "parameters": t.schema}} for t in tools]
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = self.post(f"{self.base_url}/chat/completions", headers, payload, 120)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError("server", "The provider sent an answer in an unexpected shape") from exc
        calls = []
        for c in message.get("tool_calls") or []:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            calls.append(ToolCall(id=c.get("id") or c["function"]["name"], name=c["function"]["name"],
                                  arguments=args if isinstance(args, dict) else {}))
        return Completion(text=(message.get("content") or "").strip(), tool_calls=calls)
