from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class ProviderType(StrEnum):
    PAYMENTS = "PAYMENTS"
    MESSAGING = "MESSAGING"
    VOICE = "VOICE"
    RETRY = "RETRY"
    ESCALATION = "ESCALATION"


class ReadinessStatus(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"
    TEST_READY = "TEST_READY"
    MOCK_VERIFIED = "MOCK_VERIFIED"
    TEST_VERIFIED = "TEST_VERIFIED"
    SANDBOX_VERIFIED = "SANDBOX_VERIFIED"
    LIVE_VERIFIED = "LIVE_VERIFIED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class VerificationResult(StrEnum):
    NOT_RUN = "NOT_RUN"
    SUCCESS = "SUCCESS"
    SKIPPED_LIVE_DISABLED = "SKIPPED_LIVE_DISABLED"
    FAILED = "FAILED"


class ProviderVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: StrictBool = Field(description="Explicitly authorize a safe provider test probe.")

    @field_validator("confirm")
    @classmethod
    def require_confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("explicit provider test confirmation is required")
        return value


class ProviderReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str
    provider_type: ProviderType
    implementation: str
    provider_mode: str
    readiness_status: ReadinessStatus
    last_verification_timestamp: datetime | None = None
    last_verification_result: VerificationResult = VerificationResult.NOT_RUN
    last_error_type: str | None = None
    capabilities: list[str]
    limitations: list[str]
    verification_id: str | None = None
    latency_ms: int | None = None
    idempotency_status: str | None = None


class ProviderVerificationResponse(ProviderReadinessResponse):
    operation: str
    verification_result: VerificationResult
    error_type: str | None = None
    message: str
    input_hash: str
    output_hash: str
    verification_record: dict[str, Any] | None = None

