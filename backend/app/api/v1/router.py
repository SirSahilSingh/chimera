from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.database import session_dependency
from backend.app.domain import DomainError
from backend.app.schemas import (
    CaseCreate,
    DecisionResponse,
    ExecutionResponse,
    HealthResponse,
    InterventionCreateRequest,
    InterventionEventResponse,
    InterventionExecutionResponse,
    InterventionOutcomeCreate,
    InterventionOutcomeResponse,
    InterventionResponse,
    PaginatedCases,
    RecoveryCaseResponse,
)
from backend.app.services.case_service import CaseService
from backend.app.services.intelligence_service import IntelligenceService
from backend.chimera_intelligence.schemas import ExplanationResponse
from backend.app.interventions.errors import (
    DecisionNotFoundError,
    ExecutorUnavailableError,
    InterventionError,
    InterventionNotFoundError,
)
from backend.app.interventions.service import InterventionService
from backend.chimera_voice.errors import VoiceDomainError, VoiceNotFoundError, VoiceProviderFailure
from backend.chimera_voice.schemas import (
    VoiceCallResponse,
    VoiceDemoRequest,
    VoiceEventResponse,
    VoiceHistoryResponse,
    VoiceStartRequest,
    VoiceTurnResponse,
    VoiceWebhookEvent,
)
from backend.chimera_voice.service import VoiceService
from backend.chimera_payments.errors import PaymentError, PaymentNotFoundError, PaymentProviderError, PaymentWebhookError
from backend.chimera_payments.schemas import PaymentDemoRequest, PaymentEventResponse, PaymentAttemptResponse, PaymentLinkResponse, PaymentListResponse
from backend.chimera_payments.service import PaymentService


def build_router(*, session_factory, service_factory, health_factory, intelligence_service_factory, intervention_service_factory, voice_service_factory, payment_service_factory) -> APIRouter:
    router = APIRouter()

    def db() -> Session:
        yield from session_dependency(session_factory)

    def service(session: Session = Depends(db)) -> CaseService:
        return service_factory(session)

    def intelligence_service(session: Session = Depends(db)) -> IntelligenceService:
        return intelligence_service_factory(session)

    def intervention_service(session: Session = Depends(db)) -> InterventionService:
        return intervention_service_factory(session)

    def voice_service(session: Session = Depends(db)) -> VoiceService:
        return voice_service_factory(session)

    def payment_service(session: Session = Depends(db)) -> PaymentService:
        return payment_service_factory(session)

    def as_case(case) -> RecoveryCaseResponse:
        decisions = sorted(case.decisions, key=lambda item: item.created_at, reverse=True)
        executions = sorted(case.executions, key=lambda item: item.created_at, reverse=True)
        return RecoveryCaseResponse(
            id=case.id,
            external_event_id=case.external_event_id,
            payment_id=case.payment_id,
            customer_id=case.customer_id,
            amount_paise=case.amount_paise,
            currency=case.currency,
            failure_reason=case.failure_reason,
            incident_flag=case.incident_flag,
            payment_method=case.payment_method,
            decision_timestamp=case.decision_timestamp,
            status=case.status,
            created_at=case.created_at,
            updated_at=case.updated_at,
            latest_decision=DecisionResponse.model_validate(decisions[0]) if decisions else None,
            latest_execution=ExecutionResponse.model_validate(executions[0]) if executions else None,
            audit_count=len(case.audit_logs),
        )

    def as_intervention(intervention) -> InterventionResponse:
        executions = sorted(intervention.executions, key=lambda item: (item.attempt_number, item.id))
        outcomes = sorted(intervention.outcomes, key=lambda item: (item.occurred_at, item.id))
        events = sorted(intervention.events, key=lambda item: (item.sequence_number, item.id))
        return InterventionResponse(
            id=intervention.id,
            recovery_case_id=intervention.recovery_case_id,
            decision_id=intervention.decision_id,
            action=intervention.action,
            status=intervention.status,
            priority=intervention.priority,
            idempotency_key=intervention.idempotency_key,
            created_at=intervention.created_at,
            queued_at=intervention.queued_at,
            started_at=intervention.started_at,
            completed_at=intervention.completed_at,
            updated_at=intervention.updated_at,
            lifecycle_version=intervention.lifecycle_version,
            executions=[InterventionExecutionResponse.model_validate(item) for item in executions],
            outcomes=[InterventionOutcomeResponse.model_validate(item) for item in outcomes],
            events=[InterventionEventResponse.model_validate(item) for item in events],
        )

    def as_voice_call(call) -> VoiceCallResponse:
        turns = sorted(call.turns, key=lambda item: (item.sequence_number, item.id))
        events = sorted(call.events, key=lambda item: (item.sequence_number, item.id))
        return VoiceCallResponse(
            id=call.id,
            intervention_id=call.intervention_id,
            recovery_case_id=call.recovery_case_id,
            provider=call.provider,
            provider_call_reference=call.provider_call_reference,
            status=call.status,
            scenario=call.scenario,
            idempotency_key=call.idempotency_key,
            input_hash=call.input_hash,
            transcript_hash=call.transcript_hash,
            voice_agent_version=call.voice_agent_version,
            prompt_version=call.prompt_version,
            outcome_intent=call.outcome_intent,
            payment_link=call.payment_link,
            failure_code=call.failure_code,
            created_at=call.created_at,
            started_at=call.started_at,
            completed_at=call.completed_at,
            updated_at=call.updated_at,
            lifecycle_version=call.lifecycle_version,
            turns=[VoiceTurnResponse.model_validate(item) for item in turns],
            events=[VoiceEventResponse.model_validate(item) for item in events],
        )

    def as_payment(link) -> PaymentLinkResponse:
        attempts = sorted(link.attempts, key=lambda item: (item.first_seen_at, item.id))
        events = sorted(link.events, key=lambda item: (item.occurred_at, item.id))
        return PaymentLinkResponse(
            id=link.id, recovery_case_id=link.recovery_case_id, intervention_id=link.intervention_id, decision_id=link.decision_id,
            provider=link.provider, provider_payment_link_id=link.provider_payment_link_id, short_url=link.short_url,
            amount_paise=link.amount_paise, currency=link.currency, status=link.status, idempotency_key=link.idempotency_key,
            request_hash=link.request_hash, result_hash=link.result_hash, expires_at=link.expires_at, created_at=link.created_at,
            updated_at=link.updated_at, attempts=[PaymentAttemptResponse.model_validate(item) for item in attempts],
            events=[PaymentEventResponse.model_validate(item) for item in events],
        )

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        engine, settings, model_status = health_factory()
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:
            db_status = "unavailable"
        return HealthResponse(status="ok" if db_status == "ok" and model_status == "compatible" else "degraded", database=db_status, model_compatibility=model_status, api_environment=settings.api_environment)

    @router.post("/recovery-cases", response_model=RecoveryCaseResponse, status_code=201)
    def create_case(payload: CaseCreate, case_service: CaseService = Depends(service)):
        try:
            return as_case(case_service.create_case(payload))
        except DomainError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/recovery-cases", response_model=PaginatedCases)
    def list_cases(
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
        status: str | None = None,
        failure_reason: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        case_service: CaseService = Depends(service),
    ):
        cases, total = case_service.list_cases(page=page, page_size=page_size, status=status, failure_reason=failure_reason, created_from=created_from, created_to=created_to)
        return PaginatedCases(items=[as_case(case) for case in cases], page=page, page_size=page_size, total=total)

    @router.get("/recovery-cases/{case_id}", response_model=RecoveryCaseResponse)
    def get_case(case_id: str, case_service: CaseService = Depends(service)):
        try:
            return as_case(case_service.get_case(case_id))
        except DomainError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/recovery-cases/{case_id}/decide", response_model=DecisionResponse)
    def decide(case_id: str, case_service: CaseService = Depends(service)):
        try:
            return DecisionResponse.model_validate(case_service.decide(case_service.get_case(case_id)))
        except DomainError as exc:
            raise HTTPException(status_code=409 if "status" in str(exc) else 404, detail=str(exc)) from exc

    @router.post("/recovery-cases/{case_id}/execute", response_model=ExecutionResponse)
    def execute(case_id: str, case_service: CaseService = Depends(service)):
        try:
            return ExecutionResponse.model_validate(case_service.execute(case_service.get_case(case_id)))
        except DomainError as exc:
            raise HTTPException(status_code=409 if "case" in str(exc) else 404, detail=str(exc)) from exc

    @router.get("/decisions/{decision_id}", response_model=DecisionResponse)
    def get_decision(decision_id: str, case_service: CaseService = Depends(service)):
        try:
            return DecisionResponse.model_validate(case_service.get_decision(decision_id))
        except DomainError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/decisions/{decision_id}/interventions", response_model=InterventionResponse)
    def create_intervention(
        decision_id: str,
        response: Response,
        payload: InterventionCreateRequest | None = Body(default=None),
        service: InterventionService = Depends(intervention_service),
    ):
        del payload  # The empty request is accepted for retries; action is never client-supplied.
        try:
            intervention, created = service.create_from_decision(decision_id)
            response.status_code = 201 if created else 200
            return as_intervention(intervention)
        except DecisionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InterventionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/decisions/{decision_id}/explain", response_model=ExplanationResponse, status_code=201)
    def explain(decision_id: str, explanation_service: IntelligenceService = Depends(intelligence_service)):
        try:
            return explanation_service.explain(decision_id)
        except DomainError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/decisions/{decision_id}/explanation", response_model=ExplanationResponse)
    def latest_explanation(decision_id: str, explanation_service: IntelligenceService = Depends(intelligence_service)):
        try:
            return explanation_service.latest(decision_id)
        except DomainError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/decisions/{decision_id}/explanations", response_model=list[ExplanationResponse])
    def explanation_history(decision_id: str, explanation_service: IntelligenceService = Depends(intelligence_service)):
        try:
            return explanation_service.history(decision_id)
        except DomainError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/interventions", response_model=list[InterventionResponse])
    def list_interventions(
        status: str | None = None,
        action: str | None = None,
        recovery_case_id: str | None = None,
        service: InterventionService = Depends(intervention_service),
    ):
        return [as_intervention(item) for item in service.list_interventions(status=status, action=action, recovery_case_id=recovery_case_id)]

    @router.get("/interventions/queue", response_model=list[InterventionResponse])
    def intervention_queue(service: InterventionService = Depends(intervention_service)):
        return [as_intervention(item) for item in service.list_interventions(queue_only=True)]

    @router.get("/interventions/{intervention_id}", response_model=InterventionResponse)
    def get_intervention(intervention_id: str, service: InterventionService = Depends(intervention_service)):
        try:
            return as_intervention(service.get_intervention(intervention_id))
        except InterventionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/interventions/{intervention_id}/queue", response_model=InterventionResponse)
    def queue_intervention(intervention_id: str, service: InterventionService = Depends(intervention_service)):
        try:
            return as_intervention(service.queue(intervention_id))
        except InterventionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InterventionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/interventions/{intervention_id}/execute", response_model=InterventionExecutionResponse)
    def execute_intervention(intervention_id: str, service: InterventionService = Depends(intervention_service)):
        try:
            return InterventionExecutionResponse.model_validate(service.execute(intervention_id))
        except InterventionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ExecutorUnavailableError, InterventionError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/interventions/{intervention_id}/executions", response_model=list[InterventionExecutionResponse])
    def intervention_executions(intervention_id: str, service: InterventionService = Depends(intervention_service)):
        try:
            return [InterventionExecutionResponse.model_validate(item) for item in service.executions(intervention_id)]
        except InterventionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/interventions/{intervention_id}/outcome", response_model=InterventionOutcomeResponse, status_code=201)
    def record_intervention_outcome(intervention_id: str, payload: InterventionOutcomeCreate, service: InterventionService = Depends(intervention_service)):
        try:
            return InterventionOutcomeResponse.model_validate(service.record_outcome(intervention_id, payload))
        except InterventionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InterventionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/interventions/{intervention_id}/audit", response_model=list[InterventionEventResponse])
    def intervention_audit(intervention_id: str, service: InterventionService = Depends(intervention_service)):
        try:
            return [InterventionEventResponse.model_validate(item) for item in service.events(intervention_id)]
        except InterventionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/interventions/{intervention_id}/voice/start", response_model=VoiceCallResponse)
    def start_voice(intervention_id: str, payload: VoiceStartRequest | None = Body(default=None), service: VoiceService = Depends(voice_service)):
        request = payload or VoiceStartRequest()
        try:
            call, _ = service.start(intervention_id, request.scenario)
            return as_voice_call(call)
        except VoiceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VoiceDomainError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/interventions/{intervention_id}/payment-link", response_model=PaymentLinkResponse, status_code=201)
    def create_payment_link(intervention_id: str, service: PaymentService = Depends(payment_service)):
        try:
            return as_payment(service.create_payment_link(intervention_id))
        except PaymentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PaymentError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/interventions/{intervention_id}/payments", response_model=PaymentListResponse)
    def list_payments(intervention_id: str, service: PaymentService = Depends(payment_service)):
        try:
            return PaymentListResponse(items=[as_payment(item) for item in service.list_for_intervention(intervention_id)])
        except PaymentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/payments/{payment_id}", response_model=PaymentLinkResponse)
    def get_payment(payment_id: str, service: PaymentService = Depends(payment_service)):
        try:
            return as_payment(service.get_payment(payment_id))
        except PaymentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/payments/{payment_id}/reconcile", response_model=PaymentLinkResponse)
    def reconcile_payment(payment_id: str, service: PaymentService = Depends(payment_service)):
        try:
            return as_payment(service.reconcile_payment(payment_id))
        except PaymentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PaymentError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/payments/{payment_id}/demo/complete", response_model=PaymentLinkResponse)
    def demo_complete(payment_id: str, payload: PaymentDemoRequest | None = Body(default=None), service: PaymentService = Depends(payment_service)):
        request_payload = payload or PaymentDemoRequest()
        try:
            return as_payment(service.demo_complete(payment_id, request_payload.scenario))
        except PaymentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PaymentError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/payments/webhook/{provider}", response_model=PaymentLinkResponse)
    async def payment_webhook(provider: str, request: Request, service: PaymentService = Depends(payment_service)):
        raw_body = await request.body()
        signature = request.headers.get("x-razorpay-signature") or request.headers.get("x-payment-signature") or ""
        provider_event_id = request.headers.get("x-razorpay-event-id") or request.headers.get("x-payment-event-id")
        try:
            return as_payment(service.process_webhook(provider, raw_body, signature, provider_event_id))
        except PaymentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PaymentWebhookError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PaymentError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/interventions/{intervention_id}/voice/demo", response_model=VoiceCallResponse)
    def demo_voice(intervention_id: str, payload: VoiceDemoRequest | None = Body(default=None), service: VoiceService = Depends(voice_service)):
        request = payload or VoiceDemoRequest()
        try:
            return as_voice_call(service.run_demo(intervention_id, request.scenario))
        except VoiceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VoiceDomainError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/interventions/{intervention_id}/voice", response_model=VoiceCallResponse)
    def get_voice(intervention_id: str, service: VoiceService = Depends(voice_service)):
        try:
            return as_voice_call(service.get_call_for_intervention(intervention_id))
        except VoiceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/interventions/{intervention_id}/voice/history", response_model=VoiceHistoryResponse)
    def voice_history(intervention_id: str, service: VoiceService = Depends(voice_service)):
        try:
            call = service.get_call_for_intervention(intervention_id)
            response = as_voice_call(call)
            return VoiceHistoryResponse(call=response, turns=response.turns, events=response.events)
        except VoiceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/voice/webhook/{provider}", response_model=VoiceCallResponse)
    def voice_webhook(provider: str, payload: VoiceWebhookEvent, service: VoiceService = Depends(voice_service)):
        try:
            return as_voice_call(service.handle_webhook(provider, payload))
        except VoiceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VoiceDomainError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
