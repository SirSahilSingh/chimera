from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ProviderVerification

from .providers import ProviderSpec, build_provider_specs
from .schemas import ProviderReadinessResponse, ProviderTestRequest, ProviderVerificationResponse, ReadinessStatus, VerificationResult
from .validation import initial_status, safe_error_type
from .versions import PROVIDER_HEALTH_VERSION


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class ProviderHealthError(ValueError):
    pass


class ProviderHealthService:
    """Reports provider readiness and runs only explicit, side-effect-free probes."""

    def __init__(self, session: Session, *, settings, voice_provider, payment_provider, messaging_provider, retry_provider, escalation_provider=None, speech_provider=None) -> None:
        self.session = session
        self.settings = settings
        self.specs = build_provider_specs(settings, voice_provider=voice_provider, payment_provider=payment_provider, messaging_provider=messaging_provider, retry_provider=retry_provider, escalation_provider=escalation_provider, speech_provider=speech_provider)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _spec(self, provider_name: str) -> ProviderSpec:
        try:
            return next(spec for spec in self.specs if spec.provider_name == provider_name.casefold())
        except StopIteration as exc:
            raise ProviderHealthError("provider_not_found") from exc

    def _latest(self) -> dict[str, ProviderVerification]:
        latest: dict[str, ProviderVerification] = {}
        rows = self.session.scalars(select(ProviderVerification).order_by(ProviderVerification.generated_at.desc(), ProviderVerification.id.desc()))
        for row in rows:
            latest.setdefault(row.provider_name, row)
        return latest

    def _readiness(self, spec: ProviderSpec, latest: ProviderVerification | None = None) -> dict:
        status = initial_status(configured=spec.configured, mode=spec.provider_mode, is_local=spec.is_local, live_allowed=self.settings.allow_live_execution)
        result = VerificationResult.NOT_RUN
        error_type = None
        timestamp = None
        verification_id = None
        latency_ms = None
        idempotency_status = None
        if latest is not None:
            status = latest.readiness_status
            result = latest.verification_result
            error_type = latest.error_type
            timestamp = latest.generated_at
            verification_id = latest.id
            latency_ms = latest.latency_ms
            idempotency_status = latest.idempotency_status
        return {
            "provider_name": spec.provider_name,
            "provider_type": spec.provider_type,
            "implementation": spec.implementation,
            "provider_mode": spec.provider_mode,
            "readiness_status": status,
            "last_verification_timestamp": timestamp,
            "last_verification_result": result,
            "last_error_type": error_type,
            "capabilities": list(spec.capabilities),
            "limitations": list(spec.limitations),
            "verification_id": verification_id,
            "latency_ms": latency_ms,
            "idempotency_status": idempotency_status,
        }

    def list(self) -> list[ProviderReadinessResponse]:
        latest = self._latest()
        return [ProviderReadinessResponse.model_validate(self._readiness(spec, latest.get(spec.provider_name))) for spec in self.specs]

    def get(self, provider_name: str) -> ProviderReadinessResponse:
        spec = self._spec(provider_name)
        return ProviderReadinessResponse.model_validate(self._readiness(spec, self._latest().get(spec.provider_name)))

    def _result(self, spec: ProviderSpec, *, operation: str, readiness_status: ReadinessStatus, verification_result: VerificationResult, error_type: str | None, message: str, latency_ms: int | None, idempotency_status: str = "NOT_APPLICABLE") -> ProviderVerificationResponse:
        safe_result = {"message": message, "provider_health_version": PROVIDER_HEALTH_VERSION, "operation": operation, "error_type": error_type, "mode": spec.provider_mode}
        input_hash = _hash(spec.safe_identity)
        output_hash = _hash(safe_result)
        row = ProviderVerification(
            provider_name=spec.provider_name,
            provider_type=spec.provider_type.value,
            provider_mode=spec.provider_mode,
            operation=operation,
            readiness_status=readiness_status.value,
            verification_result=verification_result.value,
            verification_result_json=safe_result,
            capabilities=list(spec.capabilities),
            error_type=error_type,
            latency_ms=latency_ms,
            idempotency_status=idempotency_status,
            input_hash=input_hash,
            output_hash=output_hash,
        )
        self.session.add(row)
        self.session.commit()
        response = self._readiness(spec, row)
        response.update({"operation": operation, "verification_result": verification_result, "error_type": error_type, "message": message, "input_hash": input_hash, "output_hash": output_hash, "verification_record": safe_result})
        return ProviderVerificationResponse.model_validate(response)

    def verify(self, provider_name: str, *, operation: str = "verify") -> ProviderVerificationResponse:
        spec = self._spec(provider_name)
        if spec.is_local:
            return self._result(spec, operation=operation, readiness_status=ReadinessStatus.MOCK_VERIFIED, verification_result=VerificationResult.SUCCESS, error_type=None, message="Local deterministic provider is available; no external request was made.", latency_ms=0)
        if not spec.configured:
            return self._result(spec, operation=operation, readiness_status=ReadinessStatus.NOT_CONFIGURED, verification_result=VerificationResult.FAILED, error_type="missing_configuration", message="Required provider configuration is missing.", latency_ms=None)
        if spec.provider_mode == "LIVE" and not self.settings.allow_live_execution:
            return self._result(spec, operation=operation, readiness_status=ReadinessStatus.CONFIGURED, verification_result=VerificationResult.SKIPPED_LIVE_DISABLED, error_type="live_execution_disabled", message="Live provider verification is disabled by CHIMERA_ALLOW_LIVE_EXECUTION.", latency_ms=None)
        if spec.probe is None:
            return self._result(spec, operation=operation, readiness_status=ReadinessStatus.FAILED, verification_result=VerificationResult.FAILED, error_type="unsupported_capability", message="This provider has no safe connectivity probe.", latency_ms=None)
        started = time.perf_counter()
        try:
            spec.probe()
        except Exception as exc:
            code = safe_error_type(getattr(exc, "code", str(exc)), "provider_unavailable")
            status = ReadinessStatus.UNAVAILABLE if code in {"provider_timeout", "provider_unavailable"} else ReadinessStatus.FAILED
            return self._result(spec, operation=operation, readiness_status=status, verification_result=VerificationResult.FAILED, error_type=code, message="Provider verification failed with a controlled error.", latency_ms=int((time.perf_counter() - started) * 1000))
        return self._result(spec, operation=operation, readiness_status=ReadinessStatus.LIVE_VERIFIED if spec.provider_mode == "LIVE" else ReadinessStatus.SANDBOX_VERIFIED if spec.provider_mode == "SANDBOX" else ReadinessStatus.TEST_VERIFIED, verification_result=VerificationResult.SUCCESS, error_type=None, message="Safe provider connectivity probe succeeded; no customer-facing action was performed.", latency_ms=int((time.perf_counter() - started) * 1000))

    def test(self, provider_name: str, request: ProviderTestRequest) -> ProviderVerificationResponse:
        spec = self._spec(provider_name)
        if spec.provider_mode not in {"TEST", "SANDBOX", "LIVE"}:
            return self._result(spec, operation="test", readiness_status=ReadinessStatus.FAILED, verification_result=VerificationResult.FAILED, error_type="provider_mode_mismatch", message="Explicit provider tests require TEST, SANDBOX, or explicitly enabled LIVE mode.", latency_ms=None)
        return self.verify(provider_name, operation="test")

    def latest_records(self) -> list[ProviderVerification]:
        return list(self.session.scalars(select(ProviderVerification).order_by(ProviderVerification.generated_at.desc(), ProviderVerification.id.desc())))
