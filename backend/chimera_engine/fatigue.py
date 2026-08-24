"""Observable, integer-paise fatigue calculation."""

from __future__ import annotations

from typing import Mapping

from backend.chimera_simulator.models import PaymentFailureEvent


def calculate_fatigue_penalty_paise(
    event: PaymentFailureEvent,
    action: str,
    fatigue_base_paise: Mapping[str, int],
) -> tuple[int, str]:
    contacts = event.context.contacts_last_7_days
    if contacts < 0:
        raise ValueError("contacts_last_7_days cannot be negative")
    base = fatigue_base_paise[action]
    penalty = base * (1 + contacts)
    return penalty, f"fatigue_base={base} paise; contacts_last_7_days={contacts}; multiplier={1 + contacts}"
