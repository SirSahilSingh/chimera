from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.app.adapters.execution import ActionExecutionAdapter, DeterministicStubExecutionAdapter
from backend.app.domain import CaseStatus, DomainError, transition
from backend.app.schemas import CaseCreate
from backend.app.services.context_builder import build_event
from backend.chimera_engine.config import DecisionEngineConfig
from backend.chimera_engine.engine import DecisionEngine
from backend.chimera_model.benchmark import (
    INTERACTION_FEATURE_SCHEMA_VERSION,
    INTERACTION_MODEL_VERSION,
    Gate4ModelAdapter,
    BenchmarkProbabilityModel,
)
from backend.chimera_model.features import build_feature_builder
from backend.chimera_simulator.config import SimulatorConfig

from backend.app.db.models import ActionExecution, AuditLog, Decision, DecisionCandidate, RecoveryCase


class CaseService:
    def __init__(self, session: Session, simulator_config: SimulatorConfig, model_path) -> None:
        self.session = session
        self.simulator_config = simulator_config
        self.model_path = model_path
        self._engine: DecisionEngine | None = None

    def engine(self) -> DecisionEngine:
        if self._engine is None:
            selected = BenchmarkProbabilityModel.load(
                self.model_path,
                expected_simulator_version=self.simulator_config.simulator_version,
                expected_config_hash=self.simulator_config.config_hash,
            )
            self._engine = DecisionEngine(
                Gate4ModelAdapter(
                    selected,
                    build_feature_builder().schema,
                    DecisionEngineConfig().compatible_model_version,
                ),
                self.simulator_config,
            )
        return self._engine

    def create_case(self, payload: CaseCreate) -> RecoveryCase:
        case = RecoveryCase(**payload.model_dump())
        try:
            self.session.add(case)
            self.session.flush()
            self._audit(case, "CASE_CREATED", {"external_event_id": case.external_event_id})
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise DomainError("external_event_id already exists") from exc
        self.session.refresh(case)
        return case

    def get_case(self, case_id: str) -> RecoveryCase:
        result = self.session.execute(
            select(RecoveryCase)
            .options(joinedload(RecoveryCase.decisions).joinedload(Decision.candidates), joinedload(RecoveryCase.executions))
            .where(RecoveryCase.id == case_id)
        )
        case = result.unique().scalar_one_or_none()
        if case is None:
            raise DomainError("recovery case not found")
        return case

    def list_cases(self, *, page: int, page_size: int, status: str | None, failure_reason: str | None, created_from: datetime | None, created_to: datetime | None):
        query = select(RecoveryCase).order_by(RecoveryCase.created_at.desc())
        count_query = select(func.count()).select_from(RecoveryCase)
        filters = []
        if status:
            filters.append(RecoveryCase.status == status)
        if failure_reason:
            filters.append(RecoveryCase.failure_reason == failure_reason)
        if created_from:
            filters.append(RecoveryCase.created_at >= created_from)
        if created_to:
            filters.append(RecoveryCase.created_at <= created_to)
        query = query.where(*filters).offset((page - 1) * page_size).limit(page_size)
        count_query = count_query.where(*filters)
        return list(self.session.scalars(query)), int(self.session.scalar(count_query) or 0)

    def decide(self, case: RecoveryCase) -> Decision:
        if case.status not in {CaseStatus.NEW.value, CaseStatus.DECIDED.value}:
            raise DomainError(f"case status {case.status} cannot be decided")
        event = build_event(case, self.simulator_config)
        result = self.engine().decide(event)
        decision_run_id = uuid4().hex
        selected = result.candidate(result.selected_action)
        trace = result.to_dict()
        trace["application_model_version"] = INTERACTION_MODEL_VERSION
        trace["application_feature_schema_version"] = INTERACTION_FEATURE_SCHEMA_VERSION
        decision = Decision(
            recovery_case_id=case.id,
            decision_run_id=decision_run_id,
            selected_action=result.selected_action,
            predicted_probability=selected.predicted_probability,
            expected_gross_recovery_paise=selected.expected_gross_recovery_paise,
            expected_net_value_paise=selected.expected_net_value_paise,
            model_version=INTERACTION_MODEL_VERSION,
            feature_schema_version=INTERACTION_FEATURE_SCHEMA_VERSION,
            engine_version=result.engine_version,
            simulator_version=None,
            prompt_version=None,
            decision_timestamp=result.decision_timestamp,
            trace_json=trace,
        )
        for candidate in result.candidates:
            decision.candidates.append(DecisionCandidate(decision=decision, **candidate.to_dict()))
        self.session.add(decision)
        if case.status == CaseStatus.NEW.value:
            transition(case.status, CaseStatus.DECIDED)
            case.status = CaseStatus.DECIDED.value
        case.updated_at = datetime.now(case.decision_timestamp.tzinfo)
        self._audit(case, "DECISION_COMPLETED", {"decision_run_id": decision_run_id, "selected_action": result.selected_action}, decision=decision)
        self.session.commit()
        self.session.refresh(decision)
        return decision

    def latest_decision(self, case: RecoveryCase) -> Decision | None:
        result = self.session.execute(
            select(Decision)
            .options(joinedload(Decision.candidates))
            .where(Decision.recovery_case_id == case.id)
            .order_by(Decision.created_at.desc())
        )
        return result.unique().scalars().first()

    def get_decision(self, decision_id: str) -> Decision:
        result = self.session.execute(
            select(Decision).options(joinedload(Decision.candidates)).where(Decision.id == decision_id)
        )
        decision = result.unique().scalar_one_or_none()
        if decision is None:
            raise DomainError("decision not found")
        return decision

    def execute(self, case: RecoveryCase, adapter: ActionExecutionAdapter | None = None) -> ActionExecution:
        decision = self.latest_decision(case)
        if decision is None:
            raise DomainError("case must have a decision before execution")
        if case.status not in {CaseStatus.DECIDED.value, CaseStatus.ACTION_EXECUTED.value}:
            raise DomainError(f"case status {case.status} cannot execute an action")
        key = hashlib.sha256(f"{case.id}|{decision.selected_action}|{decision.decision_run_id}".encode()).hexdigest()
        existing = self.session.scalar(select(ActionExecution).where(ActionExecution.idempotency_key == key))
        if existing is not None:
            return existing
        if case.status == CaseStatus.DECIDED.value:
            transition(case.status, CaseStatus.ACTION_PENDING)
            case.status = CaseStatus.ACTION_PENDING.value
        execution = ActionExecution(
            recovery_case_id=case.id,
            decision_id=decision.id,
            action=decision.selected_action,
            provider_mode="LOCAL",
            status="PENDING",
            idempotency_key=key,
            request_json={"action": decision.selected_action, "amount_paise": case.amount_paise},
        )
        self.session.add(execution)
        self.session.flush()
        result = (adapter or DeterministicStubExecutionAdapter()).execute(
            action=execution.action, idempotency_key=key, amount_paise=case.amount_paise
        )
        execution.status = result.status
        execution.provider_reference = result.provider_reference
        execution.response_json = result.response
        execution.executed_at = datetime.now(case.decision_timestamp.tzinfo)
        transition(case.status, CaseStatus.ACTION_EXECUTED)
        case.status = CaseStatus.ACTION_EXECUTED.value
        case.updated_at = execution.executed_at
        self._audit(case, "ACTION_EXECUTED", {"action": execution.action, "idempotency_key": key}, decision=decision)
        self.session.commit()
        self.session.refresh(execution)
        return execution

    def _audit(self, case: RecoveryCase, event_type: str, payload: dict, decision: Decision | None = None) -> None:
        self.session.add(AuditLog(recovery_case_id=case.id, decision_id=decision.id if decision else None, event_type=event_type, actor="system", payload_json=payload))
