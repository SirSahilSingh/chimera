from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.db.models import AuditLog, Decision, Explanation
from backend.app.domain import DomainError
from backend.chimera_intelligence.agent import ExplanationAgent
from backend.chimera_intelligence.context import build_intelligence_context
from backend.chimera_simulator.config import SimulatorConfig


class IntelligenceService:
    """Persist one immutable explanation record per explicit API request."""

    def __init__(self, session: Session, simulator_config: SimulatorConfig, agent: ExplanationAgent) -> None:
        self.session = session
        self.simulator_config = simulator_config
        self.agent = agent

    def _get_decision(self, decision_id: str) -> Decision:
        result = self.session.execute(
            select(Decision)
            .options(joinedload(Decision.candidates), joinedload(Decision.recovery_case))
            .where(Decision.id == decision_id)
        )
        decision = result.unique().scalar_one_or_none()
        if decision is None:
            raise DomainError("decision not found")
        return decision

    def explain(self, decision_id: str) -> Explanation:
        decision = self._get_decision(decision_id)
        context = build_intelligence_context(decision.recovery_case, decision, self.simulator_config)
        result = self.agent.explain(context)
        explanation = Explanation(
            decision_id=decision.id,
            recovery_case_id=decision.recovery_case_id,
            explanation_source=result.explanation_source,
            provider=result.provider,
            model_name=result.model_name,
            prompt_version=result.prompt_version,
            explanation_version=result.explanation_version,
            input_context_hash=result.input_context_hash,
            output_hash=result.output_hash,
            fallback_reason=result.fallback_reason,
            structured_explanation=result.structured_explanation.model_dump(mode="json"),
        )
        self.session.add(explanation)
        self.session.flush()
        self.session.add(
            AuditLog(
                recovery_case_id=decision.recovery_case_id,
                decision_id=decision.id,
                event_type="EXPLANATION_GENERATED",
                actor="system",
                payload_json={
                    "explanation_id": explanation.id,
                    "explanation_source": result.explanation_source,
                    "fallback_reason": result.fallback_reason,
                    "input_context_hash": result.input_context_hash,
                    "output_hash": result.output_hash,
                },
            )
        )
        self.session.commit()
        self.session.refresh(explanation)
        return explanation

    def latest(self, decision_id: str) -> Explanation:
        self._get_decision(decision_id)
        explanation = self.session.scalar(
            select(Explanation)
            .where(Explanation.decision_id == decision_id)
            .order_by(Explanation.generated_at.desc(), Explanation.id.desc())
        )
        if explanation is None:
            raise DomainError("explanation not found")
        return explanation

    def history(self, decision_id: str) -> list[Explanation]:
        self._get_decision(decision_id)
        return list(
            self.session.scalars(
                select(Explanation)
                .where(Explanation.decision_id == decision_id)
                .order_by(Explanation.generated_at.desc(), Explanation.id.desc())
            )
        )
