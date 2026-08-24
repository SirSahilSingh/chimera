"""Explicit deterministic action constraint rules."""

from __future__ import annotations

from dataclasses import dataclass

from backend.chimera_simulator.models import CONTACT_ACTIONS, PaymentFailureEvent


@dataclass(frozen=True)
class ConstraintResult:
    permissible: bool
    reason: str | None


def _clock_minutes(value: str) -> int:
    hour_text, minute_text = value.split(":")
    hour, minute = int(hour_text), int(minute_text)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"invalid contact-window time: {value}")
    return hour * 60 + minute


def contact_window_eligible(event: PaymentFailureEvent, action: str) -> bool:
    if action not in CONTACT_ACTIONS or not event.action_is_outbound.get(action, False):
        return True
    start = _clock_minutes(event.contact_window.start_local)
    end = _clock_minutes(event.contact_window.end_local)
    current = event.context.hour * 60
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def evaluate_constraints(event: PaymentFailureEvent, action: str) -> ConstraintResult:
    if action not in event.available_actions:
        return ConstraintResult(False, "unavailable_action")
    if action in CONTACT_ACTIONS and not contact_window_eligible(event, action):
        return ConstraintResult(False, "outside_contact_window")
    # The frozen ObservableContext has no pending-promise field. The engine does
    # not infer promise-to-pay from hidden truth or from an unqualified response.
    return ConstraintResult(True, None)
