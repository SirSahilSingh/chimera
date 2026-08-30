"""Populate a resettable, synthetic operator-demo case set.

The script uses the existing CaseService, decision engine, and orchestration
services. It never writes hidden simulator state or overrides a stored action.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.models import RecoveryCase
from backend.app.main import create_app
from backend.app.schemas import CaseCreate
from backend.app.services.case_service import CaseService
from backend.chimera_messaging.service import MessagingService
from backend.chimera_orchestration.service import RecoveryOrchestrator
from backend.chimera_payments.schemas import PaymentDemoScenario
from backend.chimera_payments.service import PaymentService
from backend.chimera_retry.service import RetryService
from backend.chimera_simulator.config import SimulatorConfig
from backend.chimera_simulator.models import ACTIONS
from backend.chimera_voice.schemas import VoiceScenario
from backend.chimera_voice.service import VoiceService


SEED_PREFIX = "synthetic-seed-v1-"


@dataclass(frozen=True)
class SeedSpec:
    name: str
    failure_reason: str
    amount_paise: int
    incident_flag: bool
    payment_method: str
    desired_demo: str
    hour: int = 10


SEED_SPECS = (
    SeedSpec("expired-small", "expired_method", 75000, False, "card", "recover"),
    SeedSpec("expired-medium", "expired_method", 1250000, False, "card", "recover"),
    SeedSpec("expired-high", "expired_method", 8500000, False, "card", "recover"),
    SeedSpec("issuer-card", "issuer_decline", 150000, False, "card", "intervene"),
    SeedSpec("issuer-upi", "issuer_decline", 750000, False, "upi", "escalate"),
    SeedSpec("issuer-high", "issuer_decline", 9500000, False, "netbanking", "escalate"),
    SeedSpec("funds-small", "insufficient_funds", 50000, False, "upi", "intervene"),
    SeedSpec("funds-medium", "insufficient_funds", 1000000, False, "card", "intervene"),
    SeedSpec("funds-high", "insufficient_funds", 12000000, False, "upi", "escalate"),
    SeedSpec("gateway-1", "technical_degradation", 90000, True, "card", "intervene"),
    SeedSpec("gateway-2", "technical_degradation", 600000, True, "upi", "intervene"),
    SeedSpec("gateway-3", "technical_degradation", 1800000, True, "netbanking", "intervene"),
    SeedSpec("abandon-small", "abandonment", 100000, False, "upi", "intervene"),
    SeedSpec("abandon-medium", "abandonment", 1500000, False, "card", "intervene"),
    SeedSpec("abandon-high", "abandonment", 9000000, False, "card", "intervene"),
    SeedSpec("retry-small", "issuer_decline", 65000, True, "card", "intervene"),
    SeedSpec("retry-medium", "technical_degradation", 1000000, True, "card", "intervene"),
    SeedSpec("voice-medium", "insufficient_funds", 1000000, False, "netbanking", "recover", 8),
    SeedSpec("escalate-medium", "insufficient_funds", 500000, False, "netbanking", "escalate", 2),
    SeedSpec("do-nothing-low", "expired_method", 1, True, "card", "idle", 0),
    SeedSpec("do-nothing-small", "issuer_decline", 1, False, "upi", "idle", 1),
    SeedSpec("blocked-high", "issuer_decline", 15000000, False, "card", "blocked-evidence", 0),
    SeedSpec("blocked-gateway", "technical_degradation", 20000000, True, "netbanking", "blocked-evidence", 1),
    SeedSpec("send-message", "insufficient_funds", 50000, False, "netbanking", "intervene", 14),
    SeedSpec("intervene-medium", "abandonment", 750000, False, "card", "intervene"),
)


def _payload(spec: SeedSpec, index: int) -> CaseCreate:
    timestamp = datetime(2026, 8, 27, spec.hour, tzinfo=timezone.utc)
    token = f"{index:02d}-{spec.name}"
    return CaseCreate(
        external_event_id=f"{SEED_PREFIX}{token}",
        payment_id=f"synthetic-payment-{token}",
        customer_id=f"synthetic-customer-{token}",
        amount_paise=spec.amount_paise,
        currency="INR",
        failure_reason=spec.failure_reason,
        incident_flag=spec.incident_flag,
        payment_method=spec.payment_method,
        decision_timestamp=timestamp,
    )


def _reset(session) -> int:
    cases = list(session.scalars(select(RecoveryCase).where(RecoveryCase.external_event_id.like(f"{SEED_PREFIX}%"))))
    for case in cases:
        session.delete(case)
    session.commit()
    return len(cases)


def _advance_case(case_service: CaseService, orchestration: RecoveryOrchestrator, decision, mode: str) -> str:
    from backend.app.interventions.service import InterventionService

    interventions = InterventionService(case_service.session)
    intervention, _ = interventions.create_from_decision(decision.id)
    if decision.selected_action == "DO_NOTHING":
        return "DO_NOTHING"
    interventions.queue(intervention.id)
    if mode == "recover" and decision.selected_action == "PAYMENT_LINK":
        payment = orchestration.payments.create_payment_link(intervention.id)
        orchestration.payments.demo_complete(payment.id, PaymentDemoScenario.PAYMENT_SUCCESS)
        return "RECOVERED"
    if mode == "recover" and decision.selected_action == "VOICE_RECOVERY":
        call = orchestration.voice.run_demo(intervention.id, VoiceScenario.CUSTOMER_REQUESTS_PAYMENT_LINK)
        links = orchestration.payments.list_for_intervention(intervention.id)
        if links:
            orchestration.payments.demo_complete(links[-1].id, PaymentDemoScenario.PAYMENT_SUCCESS)
        return "RECOVERED" if call else "INTERVENING"
    if decision.selected_action == "ESCALATE":
        orchestration.escalations.create(intervention.id, "Synthetic high-value case routed for human review")
        return "ESCALATED"
    if decision.selected_action in {"RETRY_LATER", "RETRY_NOW"}:
        orchestration.route(intervention.id)
        return "INTERVENING"
    if decision.selected_action == "SEND_MESSAGE":
        orchestration.route(intervention.id)
        return "INTERVENING"
    return "INTERVENING"


def seed(database_url: str, *, reset: bool) -> dict[str, object]:
    app = create_app(database_url, create_tables=True)
    session = app.state.session_factory()
    try:
        removed = _reset(session) if reset else 0
        simulator_config = SimulatorConfig.from_file(app.state.settings.simulator_config_path)
        service = CaseService(session, simulator_config, app.state.settings.model_artifact_path)
        payments = PaymentService(session, app.state.payment_provider)
        voice = VoiceService(session, app.state.voice_provider, payment_service=payments)
        messaging = MessagingService(session, app.state.messaging_provider, payment_service=payments)
        retry = RetryService(session, app.state.retry_provider)
        orchestration = RecoveryOrchestrator(session, messaging, retry, payments, voice)
        statuses: dict[str, int] = {}
        actions: dict[str, int] = {action: 0 for action in ACTIONS}
        blocked_evidence = 0
        for index, spec in enumerate(SEED_SPECS, start=1):
            case = service.create_case(_payload(spec, index))
            decision = service.decide(case)
            actions[decision.selected_action] += 1
            if spec.desired_demo == "blocked-evidence" and any(candidate.status == "BLOCKED" for candidate in decision.candidates):
                blocked_evidence += 1
            outcome = _advance_case(service, orchestration, decision, spec.desired_demo)
            statuses[outcome] = statuses.get(outcome, 0) + 1
        return {"created": len(SEED_SPECS), "removed": removed, "actions": actions, "outcomes": statuses, "blocked_policy_evidence": blocked_evidence}
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="sqlite+pysqlite:///./chimera.db")
    parser.add_argument("--reset", action="store_true", help="remove the previous synthetic-seed-v1 batch first")
    args = parser.parse_args()
    print(seed(args.database_url, reset=args.reset))


if __name__ == "__main__":
    main()
