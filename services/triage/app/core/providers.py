"""Server-only LLM provider selection. Runtime keys are transient and never persisted.

The single-process runtime override is intended for a local/admin-only console.
Production uses environment-injected secrets and a durable external worker.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from .settings import settings

ProviderName = Literal["openai", "gemini", "openrouter"]

ENDPOINTS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openrouter": "https://openrouter.ai/api/v1",
}

MODEL_DEFAULTS = {
    "openai": ("gpt-4.1-mini", "gpt-4.1"),
    "gemini": ("gemini-2.5-flash", "gemini-2.5-pro"),
    "openrouter": ("google/gemini-2.5-flash", "google/gemini-2.5-pro"),
}


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: ProviderName
    api_key: SecretStr | None = Field(default=None, description="Write only; omit to reuse same-provider key")
    cheap_model: str = Field(min_length=2, max_length=120)
    strong_model: str = Field(min_length=2, max_length=120)

    @field_validator("cheap_model", "strong_model")
    @classmethod
    def valid_model(cls, name: str) -> str:
        name = name.strip()
        if not name or any(c.isspace() or ord(c) < 32 for c in name):
            raise ValueError("Model must be a non-empty provider model ID without whitespace")
        return name


@dataclass(frozen=True, repr=False)
class ActiveProvider:
    provider: ProviderName
    api_key: str
    base_url: str
    cheap_model: str
    strong_model: str
    source: Literal["environment", "session"]

    def public(self) -> dict:
        """Do not reveal credentials or key-derived hints to the browser."""
        return {
            "provider": self.provider,
            "configured": bool(self.api_key),
            "source": self.source,
            "cheap_model": self.cheap_model,
            "strong_model": self.strong_model,
        }


_override: ActiveProvider | None = None
_lock = RLock()


def environmental_provider() -> ActiveProvider:
    c = settings()
    name = c.llm_provider
    keys = {
        "openai": c.openai_api_key,
        "gemini": c.gemini_api_key,
        "openrouter": c.openrouter_api_key,
    }
    cheap, strong = MODEL_DEFAULTS[name]
    return ActiveProvider(
        provider=name,
        api_key=keys[name].strip(),
        base_url=c.openai_base_url if name == "openai" else ENDPOINTS[name],
        cheap_model=(c.llm_cheap_model or cheap).strip(),
        strong_model=(c.llm_strong_model or strong).strip(),
        source="environment",
    )


def current_provider() -> ActiveProvider:
    with _lock:
        return _override if _override is not None else environmental_provider()


def choose_provider(update: ProviderUpdate) -> dict:
    global _override
    with _lock:
        previous = _override if _override and _override.provider == update.provider else None
        env = settings()
        env_key = {
            "openai": env.openai_api_key,
            "gemini": env.gemini_api_key,
            "openrouter": env.openrouter_api_key,
        }[update.provider]
        incoming = update.api_key.get_secret_value().strip() if update.api_key else ""
        key = incoming or (previous.api_key if previous else "") or env_key.strip()
        if not key:
            raise ValueError("An API key is required for this provider. Paste one or configure it in .env")
        _override = ActiveProvider(
            provider=update.provider,
            api_key=key,
            base_url=env.openai_base_url if update.provider == "openai" else ENDPOINTS[update.provider],
            cheap_model=update.cheap_model,
            strong_model=update.strong_model,
            source="session",
        )
        return _override.public()


def clear_provider_override() -> dict:
    global _override
    with _lock:
        _override = None
        return environmental_provider().public()


async def check_provider_credentials(provider: ActiveProvider | None = None) -> dict:
    """Non-generative authentication probe. No student data or model costs.

    OpenRouter models list is public; /key is used to actually validate its token.
    """
    active = provider or current_provider()
    if not active.api_key:
        return {"ok": False, "provider": active.provider, "message": "No API key configured"}
    resource = "/key" if active.provider == "openrouter" else "/models"
    url = active.base_url.rstrip("/") + resource
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=False) as http:
            response = await http.get(url, headers={"Authorization": f"Bearer {active.api_key}"})
        if response.status_code == 200:
            return {"ok": True, "provider": active.provider, "message": "Credential accepted. Model availability and JSON-mode support are checked during actual inference."}
        return {"ok": False, "provider": active.provider, "message": f"Provider authentication check failed (HTTP {response.status_code})."}
    except httpx.HTTPError:
        return {"ok": False, "provider": active.provider, "message": "Provider request failed. Check network connectivity and retry."}
