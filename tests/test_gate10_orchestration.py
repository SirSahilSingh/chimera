from __future__ import annotations

import hashlib
import hmac
import json
import unittest
import base64
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from backend.app.db.models import Decision, EscalationEvent, MessageAttempt, MessagingEvent, RecoveryCase, RetryAttempt, ScheduledRetry
from backend.app.main import create_app
from backend.chimera_messaging.context import MessagingContext
from backend.chimera_messaging.local_provider import LocalDeterministicMessagingProvider
from backend.chimera_messaging.service import MessagingService
from backend.chimera_messaging.templates import render_message
from backend.chimera_messaging.twilio_provider import TwilioMessagingProvider
from backend.chimera_orchestration.schemas import EscalationStatus
from backend.chimera_orchestration.service import EscalationService
from backend.chimera_retry.context import RetryContext
from backend.chimera_retry.provider import RetryProvider, RetryResult
from backend.chimera_retry.service import RetryService


class FailingMessageProvider(LocalDeterministicMessagingProvider):
    def send_message(self, context, content, idempotency_key):
        raise TimeoutError("provider secret should not persist")


class FailingRetryProvider(RetryProvider):
    name = "test"

    def retry(self, context: RetryContext) -> RetryResult:
        raise TimeoutError("private provider details")


class Gate10Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("sqlite+pysqlite:///:memory:")
        self.client = TestClient(self.app)

    def make_intervention(self, action: str, suffix: str, *, decision_timestamp: datetime | None = None) -> dict:
        session = self.app.state.session_factory()
        timestamp = decision_timestamp or datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        case = RecoveryCase(external_event_id=f"gate10-event-{suffix}", payment_id=f"gate10-payment-{suffix}", customer_id=f"synthetic-{suffix}", amount_paise=12500, currency="INR", failure_reason="technical_degradation", incident_flag=False, payment_method="card", decision_timestamp=timestamp, status="DECIDED")
        session.add(case)
        session.flush()
        decision = Decision(recovery_case_id=case.id, decision_run_id=f"gate10-run-{suffix}", selected_action=action, predicted_probability=0.5, expected_gross_recovery_paise=6250, expected_net_value_paise=5000, model_version="test", feature_schema_version="test", engine_version="test", decision_timestamp=timestamp, trace_json={"selected_action": action})
        session.add(decision)
        session.commit()
        decision_id = decision.id
        session.close()
        created = self.client.post(f"/api/v1/decisions/{decision_id}/interventions")
        self.assertEqual(created.status_code, 201, created.text)
        queued = self.client.post(f"/api/v1/interventions/{created.json()['id']}/queue")
        self.assertEqual(queued.status_code, 200, queued.text)
        return queued.json()

    def test_message_template_is_deterministic_and_context_is_strict(self):
        context = MessagingContext(intervention_id="i", recovery_case_id="c", decision_id="d", selected_action="SEND_MESSAGE", customer_id="synthetic", language="hi", amount_paise=12500, currency="INR", payment_method="card", failure_reason="technical_degradation", incident_flag=False, payment_link="https://demo.chimera.local/payment/x")
        self.assertEqual(render_message(context), render_message(context))
        invalid = context.model_dump()
        invalid["customer_segment"] = "LOW_ENGAGEMENT"
        with self.assertRaises(ValidationError):
            MessagingContext.model_validate(invalid)

    def test_send_message_reuses_link_and_is_idempotent(self):
        intervention = self.make_intervention("SEND_MESSAGE", "message")
        first = self.client.post(f"/api/v1/interventions/{intervention['id']}/message/send")
        second = self.client.post(f"/api/v1/interventions/{intervention['id']}/message/send")
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(first.json()["delivery_state"], "DELIVERED")
        payments = self.client.get(f"/api/v1/interventions/{intervention['id']}/payments").json()["items"]
        self.assertEqual(len(payments), 1)

    def test_message_delivery_webhook_is_signed_duplicate_safe(self):
        intervention = self.make_intervention("SEND_MESSAGE", "message-webhook")
        message = self.client.post(f"/api/v1/interventions/{intervention['id']}/message/send").json()
        event = {"provider_event_id": "delivery-1", "provider_message_id": message["provider_message_id"], "event_type": "delivered", "delivery_state": "DELIVERED", "occurred_at": "2026-01-02T12:00:00+00:00"}
        raw = json.dumps(event, separators=(",", ":")).encode()
        provider = self.app.state.messaging_provider
        signature = provider.sign(raw)
        first = self.client.post("/api/v1/messaging/webhook/local", content=raw, headers={"x-messaging-signature": signature})
        duplicate = self.client.post("/api/v1/messaging/webhook/local", content=raw, headers={"x-messaging-signature": signature})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        session = self.app.state.session_factory()
        self.assertEqual(session.query(MessagingEvent).count(), 2)
        session.close()

    def test_message_provider_failure_is_safe_and_persisted(self):
        intervention = self.make_intervention("SEND_MESSAGE", "message-failure")
        session = self.app.state.session_factory()
        service = MessagingService(session, FailingMessageProvider())
        with self.assertRaisesRegex(ValueError, "provider_request_failed"):
            service.send(intervention["id"])
        row = session.query(MessageAttempt).filter_by(intervention_id=intervention["id"]).one()
        self.assertEqual(row.status, "FAILED")
        self.assertNotIn("private", json.dumps({"status": row.status, "delivery_state": row.delivery_state}).lower())
        session.close()

    def test_retry_now_runs_once_and_never_claims_recovery(self):
        intervention = self.make_intervention("RETRY_NOW", "retry-now")
        first = self.client.post(f"/api/v1/interventions/{intervention['id']}/retry")
        second = self.client.post(f"/api/v1/interventions/{intervention['id']}/retry")
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["status"], "AWAITING_OUTCOME")
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["status"], "AWAITING_OUTCOME")

    def test_retry_later_schedules_before_execution_and_is_deterministic(self):
        timestamp = datetime.now(timezone.utc) + timedelta(days=2)
        intervention = self.make_intervention("RETRY_LATER", "retry-later", decision_timestamp=timestamp)
        scheduled = self.client.post(f"/api/v1/interventions/{intervention['id']}/retry")
        self.assertEqual(scheduled.status_code, 201, scheduled.text)
        self.assertEqual(scheduled.json()["execution_status"], "SCHEDULED")
        self.assertEqual(self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["status"], "READY")
        not_due = self.client.post(f"/api/v1/retries/{scheduled.json()['id']}/execute")
        self.assertEqual(not_due.status_code, 409)
        self.assertEqual(self.client.post(f"/api/v1/interventions/{intervention['id']}/retry").json()["id"], scheduled.json()["id"])

    def test_due_scheduled_retry_executes_and_is_append_only(self):
        intervention = self.make_intervention("RETRY_LATER", "retry-due")
        scheduled = self.client.post(f"/api/v1/interventions/{intervention['id']}/retry").json()
        executed = self.client.post(f"/api/v1/retries/{scheduled['id']}/execute")
        self.assertEqual(executed.status_code, 200, executed.text)
        self.assertEqual(executed.json()["status"], "AWAITING_OUTCOME")
        session = self.app.state.session_factory()
        self.assertEqual(session.query(RetryAttempt).filter_by(intervention_id=intervention["id"]).count(), 1)
        session.close()

    def test_retry_provider_failure_uses_safe_controlled_result(self):
        intervention = self.make_intervention("RETRY_NOW", "retry-failure")
        session = self.app.state.session_factory()
        result = RetryService(session, FailingRetryProvider()).execute_now(intervention["id"])
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.validated_result_json["error_code"], "provider_request_failed")
        session.close()

    def test_escalation_is_real_idempotent_and_append_only(self):
        intervention = self.make_intervention("ESCALATE", "escalation")
        first = self.client.post(f"/api/v1/interventions/{intervention['id']}/escalate", json={"reason": "Needs operator review"})
        second = self.client.post(f"/api/v1/interventions/{intervention['id']}/escalate", json={"reason": "different text is not a new escalation"})
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        acknowledged = self.client.post(f"/api/v1/escalations/{first.json()['id']}/acknowledge")
        resolved = self.client.post(f"/api/v1/escalations/{first.json()['id']}/resolve")
        self.assertEqual(acknowledged.json()["status"], "ACKNOWLEDGED")
        self.assertEqual(resolved.json()["status"], "RESOLVED")
        self.assertEqual(len(resolved.json()["events"]), 3)

    def test_orchestrator_routes_stored_action_without_selection(self):
        intervention = self.make_intervention("DO_NOTHING", "nothing")
        result = self.client.post(f"/api/v1/interventions/{intervention['id']}/orchestrate")
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["status"], "COMPLETED")
        session = self.app.state.session_factory()
        self.assertEqual(session.query(MessageAttempt).count(), 0)
        self.assertEqual(session.query(RetryAttempt).count(), 0)
        self.assertEqual(session.query(ScheduledRetry).count(), 0)
        session.close()

    def test_contexts_reject_hidden_fields(self):
        context = RetryContext(intervention_id="i", recovery_case_id="c", decision_id="d", action="RETRY_NOW", amount_paise=1, currency="INR", attempt_number=1, idempotency_key="a" * 64)
        candidate = context.model_dump()
        candidate["environment_state"] = "GATEWAY_DEGRADATION"
        with self.assertRaises(ValidationError):
            RetryContext.model_validate(candidate)

    def test_twilio_signature_and_form_callback_boundary(self):
        provider = TwilioMessagingProvider("AC123", "auth-token", "+10000000000", "+19999999999", enabled=True)
        url = "https://chimera.example/api/v1/messaging/webhook/twilio"
        body = urlencode({"MessageSid": "SM123", "MessageStatus": "delivered"}).encode()
        signed = base64.b64encode(hmac.new(b"auth-token", (url + "MessageSidSM123MessageStatusdelivered").encode(), hashlib.sha1).digest()).decode()
        self.assertTrue(provider.verify_webhook(body, signed, url))
        self.assertEqual(provider.parse_webhook(body, "twilio-event-1")["provider_message_id"], "SM123")


if __name__ == "__main__":
    unittest.main()
