from __future__ import annotations

import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from backend.app.db.models import Decision, InterventionEvent, RecoveryCase
from backend.app.interventions.context import ApprovedExecutionContext, build_approved_context
from backend.app.interventions.errors import InvalidLifecycleTransitionError, TerminalInterventionError
from backend.app.interventions.executors import default_executors
from backend.app.interventions.idempotency import intervention_idempotency_key
from backend.app.interventions.service import InterventionService
from backend.app.interventions.state_machine import InterventionStatus, validate_transition
from backend.app.main import create_app


class InterventionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("sqlite+pysqlite:///:memory:")
        self.client = TestClient(self.app)

    def payload(self, suffix: str = "1") -> dict:
        return {
            "external_event_id": f"intervention-event-{suffix}",
            "payment_id": f"intervention-payment-{suffix}",
            "customer_id": f"synthetic-customer-{suffix}",
            "amount_paise": 12500,
            "currency": "INR",
            "failure_reason": "issuer_decline",
            "incident_flag": False,
            "payment_method": "card",
            "decision_timestamp": "2026-01-01T12:00:00+00:00",
        }

    def make_decision(self, suffix: str = "1") -> dict:
        case = self.client.post("/api/v1/recovery-cases", json=self.payload(suffix)).json()
        response = self.client.post(f"/api/v1/recovery-cases/{case['id']}/decide")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def make_manual_decision(self, action: str, suffix: str = "manual") -> str:
        session = self.app.state.session_factory()
        case = RecoveryCase(
            external_event_id=f"manual-event-{suffix}", payment_id=f"manual-payment-{suffix}",
            customer_id=f"manual-customer-{suffix}", amount_paise=5000, currency="INR",
            failure_reason="issuer_decline", incident_flag=False, payment_method="card",
            decision_timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc), status="DECIDED",
        )
        session.add(case)
        session.flush()
        decision = Decision(
            recovery_case_id=case.id, decision_run_id=f"manual-run-{suffix}", selected_action=action,
            predicted_probability=0.5, expected_gross_recovery_paise=2500, expected_net_value_paise=2000,
            model_version="test", feature_schema_version="test", engine_version="test",
            decision_timestamp=case.decision_timestamp, trace_json={},
        )
        session.add(decision)
        session.commit()
        decision_id = decision.id
        session.close()
        return decision_id

    def test_creation_copies_stored_action_and_rejects_override(self) -> None:
        decision = self.make_decision()
        response = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions")
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["action"], decision["selected_action"])
        invalid = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions", json={"action": "SEND_MESSAGE"})
        self.assertEqual(invalid.status_code, 422)

    def test_creation_is_deterministically_idempotent(self) -> None:
        decision = self.make_decision("idempotent")
        first = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions")
        second = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(len(self.client.get("/api/v1/interventions").json()), 1)

    def test_queue_execute_and_outcome_are_separate_lifecycle_steps(self) -> None:
        decision = self.make_decision("lifecycle")
        intervention = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions").json()
        queued = self.client.post(f"/api/v1/interventions/{intervention['id']}/queue")
        self.assertEqual(queued.status_code, 200, queued.text)
        self.assertEqual(queued.json()["status"], "READY")
        execution = self.client.post(f"/api/v1/interventions/{intervention['id']}/execute")
        self.assertEqual(execution.status_code, 200, execution.text)
        self.assertEqual(execution.json()["status"], "ACCEPTED")
        detail = self.client.get(f"/api/v1/interventions/{intervention['id']}").json()
        self.assertEqual(detail["status"], "AWAITING_OUTCOME")
        repeated = self.client.post(f"/api/v1/interventions/{intervention['id']}/execute")
        self.assertEqual(repeated.json()["id"], execution.json()["id"])
        self.assertNotEqual(detail["status"], "RECOVERED")
        outcome = self.client.post(
            f"/api/v1/interventions/{intervention['id']}/outcome",
            json={"status": "RECOVERED", "recovered_amount_paise": 5000, "currency": "INR", "occurred_at": "2026-01-02T12:00:00+00:00", "source": "test"},
        )
        self.assertEqual(outcome.status_code, 201, outcome.text)
        self.assertEqual(self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["status"], "RECOVERED")
        self.assertEqual(self.client.post(f"/api/v1/interventions/{intervention['id']}/outcome", json={"status": "FAILED", "occurred_at": "2026-01-03T12:00:00+00:00", "source": "test"}).status_code, 409)

    def test_queue_is_deterministically_ordered_and_filterable(self) -> None:
        first = self.make_decision("queue-a")
        second = self.make_decision("queue-b")
        first_intervention = self.client.post(f"/api/v1/decisions/{first['id']}/interventions").json()
        second_intervention = self.client.post(f"/api/v1/decisions/{second['id']}/interventions").json()
        self.client.post(f"/api/v1/interventions/{second_intervention['id']}/queue")
        self.client.post(f"/api/v1/interventions/{first_intervention['id']}/queue")
        queue = self.client.get("/api/v1/interventions/queue")
        self.assertEqual(queue.status_code, 200)
        self.assertEqual({item["status"] for item in queue.json()}, {"READY"})
        filtered = self.client.get("/api/v1/interventions", params={"action": first["selected_action"], "recovery_case_id": first["recovery_case_id"]})
        self.assertEqual(len(filtered.json()), 1)

    def test_do_nothing_is_explicit_terminal_record_without_executor(self) -> None:
        decision_id = self.make_manual_decision("DO_NOTHING", "nothing")
        intervention = self.client.post(f"/api/v1/decisions/{decision_id}/interventions")
        self.assertEqual(intervention.status_code, 201, intervention.text)
        self.assertEqual(intervention.json()["status"], "COMPLETED")
        self.assertEqual(self.client.post(f"/api/v1/interventions/{intervention.json()['id']}/execute").status_code, 409)
        events = self.client.get(f"/api/v1/interventions/{intervention.json()['id']}/audit").json()
        self.assertEqual(events[-1]["event_type"], "INTERVENTION_COMPLETED")
        self.assertEqual(events[-1]["payload_json"]["reason"], "No intervention selected by deterministic policy")

    def test_state_machine_rejects_terminal_reentry(self) -> None:
        validate_transition("CREATED", InterventionStatus.QUEUED)
        validate_transition("QUEUED", InterventionStatus.READY)
        validate_transition("READY", InterventionStatus.EXECUTING)
        validate_transition("EXECUTING", InterventionStatus.AWAITING_OUTCOME)
        with self.assertRaises(TerminalInterventionError):
            validate_transition("FAILED", InterventionStatus.READY)
        with self.assertRaises(TerminalInterventionError):
            validate_transition("RECOVERED", InterventionStatus.EXECUTING)

    def test_approved_context_rejects_hidden_and_future_fields(self) -> None:
        decision = self.make_decision("context")
        intervention = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions").json()
        session = self.app.state.session_factory()
        try:
            service = InterventionService(session)
            stored = service.get_intervention(intervention["id"])
            context = build_approved_context(stored)
            self.assertNotIn("hidden_state", context.model_dump())
            invalid = context.model_dump()
            invalid["hidden_state"] = {"customer_segment": "LOW_ENGAGEMENT"}
            with self.assertRaises(ValidationError):
                ApprovedExecutionContext.model_validate(invalid)
        finally:
            session.close()

    def test_all_external_actions_have_local_boundaries(self) -> None:
        for action, executor in default_executors().items():
            context = ApprovedExecutionContext(
                intervention_id="int", recovery_case_id="case", decision_id="decision", action=action,
                payment={"payment_id": "pay", "amount_paise": 1, "currency": "INR", "failure_reason": "other", "payment_method": "card", "incident_flag": False, "decision_timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc)},
            )
            result = executor.execute(context)
            self.assertEqual(result.status, "ACCEPTED")
            self.assertNotEqual(result.response.get("result"), "recovery_confirmed")

    def test_event_history_is_append_only_and_sequence_ordered(self) -> None:
        decision = self.make_decision("audit")
        intervention = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions").json()
        self.client.post(f"/api/v1/interventions/{intervention['id']}/queue")
        self.client.post(f"/api/v1/interventions/{intervention['id']}/execute")
        events = self.client.get(f"/api/v1/interventions/{intervention['id']}/audit").json()
        self.assertEqual([event["sequence_number"] for event in events], list(range(1, len(events) + 1)))
        self.assertEqual(events[0]["event_type"], "INTERVENTION_CREATED")
        self.assertEqual(events[-1]["event_type"], "AWAITING_OUTCOME")
        with self.app.state.engine.connect() as connection:
            self.assertIsNotNone(connection.execute(select(InterventionEvent.id).limit(1)).fetchone())

    def test_intervention_key_uses_stored_decision_identity(self) -> None:
        decision = self.make_decision("hash")
        intervention = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions").json()
        expected = intervention_idempotency_key(decision_id=decision["id"], decision_run_id=decision["decision_run_id"], action=decision["selected_action"])
        self.assertEqual(intervention["idempotency_key"], expected)


if __name__ == "__main__":
    unittest.main()
