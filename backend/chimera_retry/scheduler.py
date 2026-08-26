from __future__ import annotations

from datetime import datetime, timedelta, timezone


def deterministic_retry_time(decision_timestamp: datetime) -> datetime:
    """Demo policy metadata: retry one day after the stored decision timestamp."""
    base = decision_timestamp if decision_timestamp.tzinfo else decision_timestamp.replace(tzinfo=timezone.utc)
    return base + timedelta(hours=24)
