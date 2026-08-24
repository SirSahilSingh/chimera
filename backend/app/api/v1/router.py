from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.database import session_dependency
from backend.app.domain import DomainError
from backend.app.schemas import CaseCreate, DecisionResponse, ExecutionResponse, HealthResponse, PaginatedCases, RecoveryCaseResponse
from backend.app.services.case_service import CaseService


def build_router(*, session_factory, service_factory, health_factory) -> APIRouter:
    router = APIRouter()

    def db() -> Session:
        yield from session_dependency(session_factory)

    def service(session: Session = Depends(db)) -> CaseService:
        return service_factory(session)

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

    return router
