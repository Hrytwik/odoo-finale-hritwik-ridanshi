"""The configured provider: the owner's settings, with the key decrypted, and the adapter built from them."""
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import LlmSettings
from app.db.session import get_db
from app.modules.llm import crypto
from app.modules.llm.adapters import AnthropicAdapter, LlmAdapter, OpenAICompatibleAdapter

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-opus-5-5"


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
        # a hosted Anthropic model needs a key; a local or compatible server needs an address and may need no key
        return bool(self.api_key) if self.provider == "anthropic" else bool(self.base_url)


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
