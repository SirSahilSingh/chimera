from __future__ import annotations

from .schemas import ReadinessStatus

SAFE_ERROR_TYPES = frozenset({
    "missing_configuration",
    "live_execution_disabled",
    "invalid_credentials",
    "provider_timeout",
    "provider_unavailable",
    "provider_invalid_response",
    "unsupported_capability",
    "provider_request_failed",
    "provider_mode_mismatch",
})


def safe_error_type(value: object, default: str = "provider_request_failed") -> str:
    candidate = str(value).strip().casefold()
    return candidate if candidate in SAFE_ERROR_TYPES else default


def initial_status(*, configured: bool, mode: str, is_local: bool, live_allowed: bool) -> ReadinessStatus:
    normalized = str(mode).upper()
    if is_local:
        return ReadinessStatus.MOCK_VERIFIED
    if not configured:
        return ReadinessStatus.NOT_CONFIGURED
    if normalized == "LIVE" and not live_allowed:
        return ReadinessStatus.CONFIGURED
    if normalized in {"TEST", "SANDBOX"}:
        return ReadinessStatus.TEST_READY
    return ReadinessStatus.CONFIGURED

