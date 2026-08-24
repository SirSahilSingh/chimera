"""Recovery Arena adapter for CHIMERA decisions."""

from __future__ import annotations

from backend.chimera_simulator.policies import PolicySelection
from backend.chimera_simulator.models import PaymentFailureEvent

from .engine import DecisionEngine
from .models import DecisionResult


class ChimeraPolicyAdapter:
    name = "CHIMERA"

    def __init__(self, engine: DecisionEngine) -> None:
        self.engine = engine
        self.decisions: dict[str, DecisionResult] = {}

    def choose_action(self, event: PaymentFailureEvent) -> PolicySelection:
        decision = self.engine.decide(event)
        self.decisions[event.event_id] = decision
        return PolicySelection(decision.selected_action, decision.decision_reason)
