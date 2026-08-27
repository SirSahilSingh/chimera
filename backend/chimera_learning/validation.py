from __future__ import annotations

from typing import Any


FORBIDDEN_FIELDS = frozenset({
    "customer_segment", "environment_state", "natural_recovery_probability",
    "action_conditioned_probability", "hidden_state", "future_outcome",
})


def validate_learning_payload(payload: dict[str, Any]) -> None:
    """Reject simulator truth if it is accidentally handed to analytics."""
    forbidden = FORBIDDEN_FIELDS.intersection(payload)
    if forbidden:
        raise ValueError(f"learning payload contains forbidden fields: {sorted(forbidden)}")
