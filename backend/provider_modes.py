from __future__ import annotations

from enum import StrEnum


class ProviderMode(StrEnum):
    LOCAL = "LOCAL"
    MOCK = "MOCK"
    TEST = "TEST"
    LIVE = "LIVE"


def resolve_mode(provider: str, configured: str | None = None) -> str:
    if configured:
        return ProviderMode(configured.upper()).value
    return ProviderMode.LOCAL.value if provider.casefold() == "local" else ProviderMode.LIVE.value
