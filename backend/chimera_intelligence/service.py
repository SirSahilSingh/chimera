"""Read-only case intelligence projection."""

from __future__ import annotations

from typing import Any

from backend.app.services.journey_service import RecoveryJourneyService
from backend.chimera_simulator.config import SimulatorConfig

from .diagnosis import build_detection
from .insights import (
    build_decision_intelligence,
    build_explanation_summary,
    build_insights,
    build_intervention_intelligence,
    build_journey_summary,
)
from .outcome_analysis import analyze_outcome
from .root_cause import analyze_root_cause
from .schemas import RecoveryIntelligenceResponse


class RecoveryIntelligenceService:
    """Compose persisted evidence into a deterministic narrative.

    This service deliberately receives the journey projection instead of a
    model or decision engine. Reading intelligence can therefore never rerun
    inference, select a new action, create an outcome, or mutate state.
    """

    def __init__(self, journey_service: RecoveryJourneyService, simulator_config: SimulatorConfig) -> None:
        self.journey_service = journey_service
        self.simulator_config = simulator_config

    def get(self, case_id: str) -> RecoveryIntelligenceResponse:
        journey: dict[str, Any] = self.journey_service.get(case_id)
        detection = build_detection(journey, self.simulator_config)
        diagnosis = analyze_root_cause(detection)
        decision = build_decision_intelligence(journey)
        selected_action = decision.selected_action if decision else None
        intervention = build_intervention_intelligence(journey, selected_action)
        outcome = analyze_outcome(journey, selected_action)
        journey_summary = build_journey_summary(journey, outcome)
        return RecoveryIntelligenceResponse(
            case_id=case_id,
            detection=detection,
            diagnosis=diagnosis,
            decision=decision,
            intervention=intervention,
            outcome=outcome,
            journey_summary=journey_summary,
            explanation=build_explanation_summary(journey),
            insights=build_insights(detection, diagnosis, decision, intervention, outcome),
        )
