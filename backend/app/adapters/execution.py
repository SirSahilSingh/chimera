from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdapterResult:
    status: str
    provider_reference: str
    response: dict[str, str]


class ActionExecutionAdapter:
    """Future provider adapters implement this boundary; no provider is called in Gate 5."""

    def execute(self, *, action: str, idempotency_key: str, amount_paise: int) -> AdapterResult:
        raise NotImplementedError


class DeterministicStubExecutionAdapter(ActionExecutionAdapter):
    def execute(self, *, action: str, idempotency_key: str, amount_paise: int) -> AdapterResult:
        return AdapterResult(
            status="EXECUTED",
            provider_reference=f"stub:{idempotency_key[:24]}",
            response={"adapter": "deterministic_stub", "action": action, "amount_paise": str(amount_paise)},
        )
