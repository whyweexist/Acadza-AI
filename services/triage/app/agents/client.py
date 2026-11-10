"""Provider-neutral async JSON client (OpenAI, Gemini, OpenRouter)."""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
from typing import Any, TypeVar
import httpx
from pydantic import BaseModel, ValidationError
from ..core.settings import settings
from ..core.providers import ActiveProvider, current_provider
from .prompts import BASE, REGISTRY, VERSION

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AgentFailure(Exception):
    pass


class AgentClient:
    def __init__(self, db=None, provider: ActiveProvider | None = None):
        self.config = settings()
        # Freeze provider and key for the entire triage job, even if an admin switches providers.
        self.provider = provider or current_provider()
        self.sem = asyncio.Semaphore(max(1, self.config.llm_concurrency))
        self.db = db
        self.metrics: list[dict] = []

    async def call(self, role: str, payload: dict, model: type[T], strong: bool = False) -> T:
        if not self.provider.api_key:
            raise AgentFailure(f"{self.provider.provider} key absent: configure LLM_PROVIDER and its API key")
        model_name = self.provider.strong_model if strong else self.provider.cheap_model
        system_prompt = BASE + "\n" + REGISTRY[role] + "\nRequired JSON Schema: " + json.dumps(model.model_json_schema())
        message = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        cache_key = hashlib.sha256(json.dumps([VERSION, role, self.provider.provider, model_name, system_prompt, message], ensure_ascii=False).encode()).hexdigest()
        if self.db is not None:
            cached = await self.db.cache_read(cache_key)
            if cached:
                try:
                    return model.model_validate_json(cached)
                except ValidationError:
                    pass
        headers = {"Authorization": f"Bearer {self.provider.api_key}"}
        request_body = {
            "model": model_name,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
        }
        if self.provider.provider != "gemini":
            request_body["temperature"] = 0
        # Gemini thinking models may reject an explicit temperature.
        if self.provider.provider == "openrouter":
            headers["X-OpenRouter-Title"] = "Acadza Question QA"
        errors = []
        async with self.sem:
            async with httpx.AsyncClient(timeout=self.config.llm_timeout_seconds) as http:
                for attempt in range(2):
                    try:
                        response = await http.post(self.provider.base_url.rstrip("/") + "/chat/completions", headers=headers, json=request_body)
                        response.raise_for_status()
                        item = response.json()
                        raw = item["choices"][0]["message"]["content"]
                        parsed = model.model_validate_json(raw)
                        usage = item.get("usage") or {}
                        self.metrics.append({"agent": role, "provider": self.provider.provider, "model": model_name, "prompt_version": VERSION, "usage": usage, "attempt": attempt + 1})
                        if self.db is not None:
                            await self.db.cache_write(cache_key, raw)
                        return parsed
                    except (ValidationError, ValueError, KeyError, IndexError, httpx.HTTPError) as exc:
                        errors.append(type(exc).__name__)
                        log.warning("agent_error role=%s attempt=%s type=%s", role, attempt + 1, type(exc).__name__)
                        if attempt == 0:
                            await asyncio.sleep(0.4)
        # The orchestrator catches this and writes a review-needed failure record,
        # rather than inventing a valid 'defect' to satisfy the discriminated union.
        raise AgentFailure(f"{role} failed after one retry: {', '.join(errors)}")
