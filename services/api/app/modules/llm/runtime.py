"""The configured provider: the owner's settings, with the key decrypted, and the adapter built from them."""
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import LlmSettings
from app.db.session import get_db
from app.modules.llm import crypto
from app.modules.llm.adapters import AnthropicAdapter, LlmAdapter, OpenAICompatibleAdapter

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-opus-5-5"


def is_local_address(url: str) -> bool:
    """True for localhost, loopback and private-network addresses, where a model server (Ollama, LM Studio) needs no key."""
    host = (urlparse(url).hostname or "").lower()
    if host == "localhost" or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


@dataclass
class LlmConfig:
    provider: str
    model: str
    base_url: str | None
    api_key: str | None
    supports_tools: bool
    supports_vision: bool

    @property
    def configured(self) -> bool:
        # a hosted model (Anthropic, Groq, OpenAI...) needs a key; only a server on this computer or the local network may go without
        if self.api_key:
            return True
        return self.provider != "anthropic" and bool(self.base_url) and is_local_address(self.base_url)


@dataclass
class LlmRuntime:
    adapter: LlmAdapter
    config: LlmConfig


def load_config(db: Session) -> LlmConfig:
    row = db.get(LlmSettings, 1)
    if row is None:
        return LlmConfig(DEFAULT_PROVIDER, DEFAULT_MODEL, None, None, True, False)
    key = crypto.decrypt_key(row.api_key_encrypted) if row.api_key_encrypted else None
    return LlmConfig(row.provider, row.model, row.base_url, key, row.supports_tools, row.supports_vision)


def build_adapter(cfg: LlmConfig) -> LlmAdapter:
    if cfg.provider == "anthropic":
        return AnthropicAdapter(cfg.api_key or "", cfg.model)
    return OpenAICompatibleAdapter(cfg.base_url or "", cfg.model, cfg.api_key)


def get_runtime(db: Session = Depends(get_db)) -> LlmRuntime:
    """The provider to use for this request. Tests replace this dependency with a scripted adapter."""
    cfg = load_config(db)
    if not cfg.configured:
        raise AppError("AI_UNAVAILABLE", "AI unavailable. Check Settings or the connection (no provider is set up yet)", status=503)
    return LlmRuntime(build_adapter(cfg), cfg)
