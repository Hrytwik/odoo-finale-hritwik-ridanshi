"""Provider adapters: one interface, `complete(system, turns, tools, options) -> Completion`.

Both adapters speak plain HTTPS JSON through `post_json`, so there is no SDK to install and tests can swap the transport.
"""
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol

from app.modules.llm.types import AdapterError, Completion, ToolCall, ToolSpec, Turn

PostJson = Callable[[str, dict[str, str], dict, float], dict]
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


GetJson = Callable[[str, dict[str, str], float], dict]


def post_json(url: str, headers: dict[str, str], payload: dict, timeout: float = 60) -> dict:
    """POST JSON, return the JSON reply. Failures become AdapterError; the key and the request are never put in a message."""
    return _send(_request(url, headers, "POST", json.dumps(payload).encode()), timeout)


def get_json(url: str, headers: dict[str, str], timeout: float = 30) -> dict:
    """GET, return the JSON reply, with the same error rules as post_json."""
    return _send(_request(url, headers, "GET", None), timeout)


def _request(url: str, headers: dict[str, str], method: str, data: bytes | None) -> urllib.request.Request:
    # a plain User-Agent: providers behind Cloudflare (Groq among them) turn away Python's default one with a 403
    return urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "EverestMills/1.0", **headers})


def _send(request: urllib.request.Request, timeout: float) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https or the owner's own base URL)
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = _error_detail(exc)
        if exc.code in (401, 403):
            raise AdapterError("auth", "The provider refused the API key") from exc
        if exc.code == 429:
            raise AdapterError("rate_limit", "The provider's limit for this minute was reached. Wait a few seconds and ask again.",
                               retry_after=_retry_after(exc, detail)) from exc
        if exc.code == 404:
            said = f" The provider said: {detail}" if detail else ""
            raise AdapterError("bad_request", "The provider found nothing there. Check the model name, and that the address is the API address ending in /v1 (Groq: https://api.groq.com/openai/v1), not a web page." + said) from exc
        if exc.code >= 500:
            raise AdapterError("server", f"The provider had a problem ({exc.code})") from exc
        raise AdapterError("bad_request", detail or f"The provider refused the request ({exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AdapterError("unreachable", "Could not reach the provider") from exc
    except ValueError as exc:
        raise AdapterError("server", "The provider sent something unreadable") from exc


def _retry_after(exc: urllib.error.HTTPError, detail: str) -> float | None:
    """How long the provider asked us to wait: its Retry-After header, or "try again in 7.2s" / "in 350ms" in the message."""
    header = exc.headers.get("Retry-After") if exc.headers else None
    try:
        if header:
            return float(header)
    except ValueError:
        pass
    found = re.search(r"try again in ([\d.]+)\s*(ms|s)\b", detail)
    if not found:
        return None
    seconds = float(found.group(1))
    return seconds / 1000 if found.group(2) == "ms" else seconds


def _error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode())
        err = body.get("error")
        message = err.get("message") if isinstance(err, dict) else err
        return str(message)[:500] if message else ""
    except (ValueError, AttributeError, OSError):
        return ""


def _model_ids(data: dict) -> list[str]:
    """The model names in a provider's /models reply: {"data": [{"id": ...}]}."""
    rows = data.get("data") if isinstance(data, dict) else None
    return sorted({str(r["id"]) for r in rows or [] if isinstance(r, dict) and r.get("id")})


class LlmAdapter(Protocol):
    def complete(self, system: str, turns: list[Turn], tools: list[ToolSpec], options: dict | None = None) -> Completion: ...

    def models(self) -> list[str]: ...


class AnthropicAdapter:
    def __init__(self, api_key: str, model: str, post: PostJson = post_json, url: str = ANTHROPIC_URL, get: GetJson = get_json):
        self.api_key, self.model, self.post, self.url, self.get = api_key, model, post, url, get

    def models(self) -> list[str]:
        headers = {"x-api-key": self.api_key, "anthropic-version": ANTHROPIC_VERSION}
        return _model_ids(self.get(self.url.rsplit("/", 1)[0] + "/models?limit=100", headers, 30))

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

    def __init__(self, base_url: str, model: str, api_key: str | None = None, post: PostJson = post_json, get: GetJson = get_json):
        self.base_url, self.model, self.api_key, self.post, self.get = base_url.rstrip("/"), model, api_key, post, get

    def models(self) -> list[str]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return _model_ids(self.get(f"{self.base_url}/models", headers, 30))

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
