from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .fallback import FallbackReason
from .prompts import SYSTEM_PROMPT


class ProviderError(RuntimeError):
    def __init__(self, reason: FallbackReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


class ExplanationProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(self, context: dict[str, Any], prompt: str) -> Any:
        ...


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    base_url: str
    api_key: str | None
    model_name: str
    timeout_seconds: float = 10.0
    provider_name: str = "openai_compatible"

    def generate(self, context: dict[str, Any], prompt: str) -> Any:
        if not self.api_key:
            raise ProviderError(FallbackReason.MISSING_API_KEY)
        payload = {
            "model": self.model_name,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            response = httpx.post(
                self.base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(FallbackReason.PROVIDER_TIMEOUT) from exc
        except httpx.RequestError as exc:
            raise ProviderError(FallbackReason.PROVIDER_UNAVAILABLE) from exc
        if response.status_code == 429:
            raise ProviderError(FallbackReason.PROVIDER_RATE_LIMITED)
        if response.status_code >= 400:
            raise ProviderError(FallbackReason.PROVIDER_UNAVAILABLE)
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return json.loads(content)
            if isinstance(content, dict):
                return content
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise ProviderError(FallbackReason.INVALID_JSON) from exc
        raise ProviderError(FallbackReason.UNEXPECTED_PROVIDER_RESPONSE)


def provider_from_settings(settings) -> ExplanationProvider | None:
    if settings.llm_provider == "none":
        return None
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model_name=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return None
