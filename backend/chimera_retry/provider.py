from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from .context import RetryContext


@dataclass(frozen=True)
class RetryResult:
    provider_reference: str
    status: str
    validated_result: dict
    completed_at: datetime


class RetryProvider(ABC):
    name: str

    @abstractmethod
    def retry(self, context: RetryContext) -> RetryResult: ...


class LocalDeterministicRetryProvider(RetryProvider):
    name = "local"

    def retry(self, context: RetryContext) -> RetryResult:
        import hashlib
        reference = f"local-retry:{hashlib.sha256(context.idempotency_key.encode()).hexdigest()[:24]}"
        return RetryResult(reference, "AWAITING_OUTCOME", {"accepted": True, "payment_recovery_confirmed": False}, datetime.now(timezone.utc))


class UnavailableLiveRetryProvider(RetryProvider):
    name = "live"

    def retry(self, context: RetryContext) -> RetryResult:
        raise RuntimeError("provider_not_configured")
