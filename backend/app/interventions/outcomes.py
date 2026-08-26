from __future__ import annotations

from enum import StrEnum


class OutcomeStatus(StrEnum):
    PENDING = "PENDING"
    RECOVERED = "RECOVERED"
    NOT_RECOVERED = "NOT_RECOVERED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
