from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.models import Decision, PaymentEvent, PaymentLink, RecoveryCase, VoiceCall
from backend.app.main import create_app
from backend.chimera_payments.providers.local import LocalDeterministicPaymentProvider
from backend.chimera_payments.schemas import PaymentDemoScenario
from backend.chimera_messaging.context import MessagingContext
from backend.chimera_messaging.twilio_provider import TwilioMessagingProvider
from backend.provider_modes import ProviderMode, resolve_mode


class Gate11Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("sqlite+pysqlite:///:memory:")
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def make_intervention(self, action: str, suffix: str) -> dict:
        session = self.app.state.session_factory()
        timestamp = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        case = RecoveryCase(external_event_id=f"gate11-{suffix}", payment_id=f"payment-{suffix}", customer_id=f"synthetic-{suffix}", amount_paise=12500, currency="INR", failure_reason="issuer_decline", incident_flag=False, payment_method="card", decision_timestamp=timestamp, status="DECIDED")
        session.add(case)
        session.flush()
        decision = Decision(recovery_case_id=case.id, decision_run_id=f"run-{suffix}", selected_action=action, predicted_probability=0.5, expected_gross_recovery_paise=6250, expected_net_value_paise=5000, model_version="test", feature_schema_version="test", engine_version="test", decision_timestamp=timestamp, trace_json={"source": "test"})
        session.add(decision)
        session.commit()
        decision_id = decision.id
        session.close()
        created = self.client.post(f"/api/v1/decisions/{decision_id}/interventions")
        self.assertEqual(created.status_code, 201, created.text)
        if action != "DO_NOTHING":
            queued = self.client.post(f"/api/v1/interventions/{created.json()['id']}/queue")
            self.assertEqual(queued.status_code, 200, queued.text)
            return queued.json()
        return created.json()

    def test_provider_modes_are_explicit_and_persisted(self):
        self.assertEqual(resolve_mode("local"), ProviderMode.LOCAL.value)
        self.assertEqual(resolve_mode("razorpay", "test"), ProviderMode.TEST.value)
        self.assertEqual(resolve_mode("twilio", "live"), ProviderMode.LIVE.value)
        intervention = self.make_intervention("PAYMENT_LINK", "mode")
        response = self.client.post(f"/api/v1/interventions/{intervention['id']}/payment-link")
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["provider_mode"], "LOCAL")
        session = self.app.state.session_factory()
        self.assertEqual(session.scalar(select(PaymentLink).where(PaymentLink.id == response.json()["id"])).provider_mode, "LOCAL")
        session.close()

    def test_configured_test_mode_is_visible_without_contacting_provider(self):
        with patch.dict(os.environ, {"PAYMENT_PROVIDER": "razorpay", "PAYMENT_MODE": "TEST", "MESSAGING_PROVIDER": "twilio", "MESSAGING_MODE": "MOCK"}, clear=False):
            app = create_app("sqlite+pysqlite:///:memory:")
        self.assertEqual(app.state.payment_provider.mode, "TEST")
        self.assertEqual(app.state.messaging_provider.mode, "MOCK")

    def test_demo_route_uses_decision_and_intervention_authority(self):
        payload = {"external_event_id": "gate11-demo-route", "payment_id": "demo-payment", "customer_id": "synthetic-demo", "amount_paise": 129900, "currency": "INR", "failure_reason": "expired_method", "incident_flag": False, "payment_method": "card", "decision_timestamp": "2026-08-26T10:00:00+00:00"}
        invalid = dict(payload, selected_action="RETRY_NOW")
        self.assertEqual(self.client.post("/api/v1/demo/recovery", json=invalid).status_code, 422)
        response = self.client.post("/api/v1/demo/recovery", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertTrue(body["case_id"] and body["decision_id"] and body["intervention_id"])
        self.assertIn(body["selected_action"], {"PAYMENT_LINK", "SEND_MESSAGE", "RETRY_NOW", "RETRY_LATER", "VOICE_RECOVERY", "ESCALATE", "DO_NOTHING"})

    def test_journey_is_persisted_projection_and_chronological(self):
        intervention = self.make_intervention("PAYMENT_LINK", "journey")
        link = self.client.post(f"/api/v1/interventions/{intervention['id']}/payment-link")
        self.assertEqual(link.status_code, 201, link.text)
        provider: LocalDeterministicPaymentProvider = self.app.state.payment_provider
        self.assertEqual(self.client.post(f"/api/v1/payments/{link.json()['id']}/demo/complete", json={"scenario": "payment_success"}).status_code, 200)
        journey = self.client.get(f"/api/v1/recovery-cases/{intervention['recovery_case_id']}/journey")
        self.assertEqual(journey.status_code, 200, journey.text)
        body = journey.json()
        self.assertEqual(body["decision"]["selected_action"], "PAYMENT_LINK")
        self.assertEqual(body["payments"][0]["provider_mode"], "LOCAL")
        timestamps = [row["timestamp"] for row in body["audit_trail"]]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertEqual(body["payments"][0]["status"], "PAID")
        self.assertNotIn("chimera-local-payment-secret", json.dumps(body))

    def test_journey_does_not_recompute_decision(self):
        intervention = self.make_intervention("DO_NOTHING", "no-recompute")
        with patch("backend.app.services.case_service.CaseService.decide", side_effect=AssertionError("must not decide while reading journey")):
            response = self.client.get(f"/api/v1/recovery-cases/{intervention['recovery_case_id']}/journey")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["decision"]["selected_action"], "DO_NOTHING")

    def test_payment_webhook_event_mode_is_persisted_and_duplicate_safe(self):
        intervention = self.make_intervention("PAYMENT_LINK", "webhook-mode")
        link = self.client.post(f"/api/v1/interventions/{intervention['id']}/payment-link").json()
        provider: LocalDeterministicPaymentProvider = self.app.state.payment_provider
        event = provider.demo_event(link["provider_payment_link_id"], PaymentDemoScenario.PAYMENT_SUCCESS)
        raw = event.model_dump_json().encode()
        headers = {"x-payment-signature": provider.sign(event)}
        self.assertEqual(self.client.post("/api/v1/payments/webhook/local", content=raw, headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/payments/webhook/local", content=raw, headers=headers).status_code, 200)
        session = self.app.state.session_factory()
        events = list(session.scalars(select(PaymentEvent).where(PaymentEvent.payment_link_id == link["id"])))
        self.assertEqual(len(events), 2)
        self.assertTrue(all(event.provider_mode == "LOCAL" for event in events))
        session.close()

    def test_do_nothing_has_no_external_provider_records(self):
        intervention = self.make_intervention("DO_NOTHING", "terminal")
        response = self.client.post(f"/api/v1/interventions/{intervention['id']}/orchestrate")
        self.assertEqual(response.status_code, 200, response.text)
        session = self.app.state.session_factory()
        self.assertEqual(session.query(PaymentLink).count(), 0)
        self.assertEqual(session.query(VoiceCall).count(), 0)
        session.close()

    def test_voice_message_and_retry_records_carry_provider_mode(self):
        voice = self.make_intervention("VOICE_RECOVERY", "voice-mode")
        started = self.client.post(f"/api/v1/interventions/{voice['id']}/voice/start")
        self.assertEqual(started.status_code, 200, started.text)
        retry = self.make_intervention("RETRY_LATER", "retry-mode")
        scheduled = self.client.post(f"/api/v1/interventions/{retry['id']}/retry")
        self.assertEqual(scheduled.status_code, 201, scheduled.text)
        message = self.make_intervention("SEND_MESSAGE", "message-mode")
        sent = self.client.post(f"/api/v1/interventions/{message['id']}/message/send")
        self.assertEqual(sent.status_code, 201, sent.text)
        self.assertEqual(started.json()["provider_mode"], "LOCAL")
        self.assertEqual(scheduled.json()["provider_mode"], "LOCAL")
        self.assertEqual(sent.json()["provider_mode"], "LOCAL")

    def test_twilio_http_boundary_is_exercised_only_with_mocked_transport(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"sid":"SM-gate11"}'

        provider = TwilioMessagingProvider("AC123", "server-secret", "+10000000000", "+19999999999", enabled=True, mode="TEST")
        context = MessagingContext(intervention_id="i", recovery_case_id="c", decision_id="d", selected_action="SEND_MESSAGE", customer_id="synthetic", language="en", amount_paise=100, currency="INR", payment_method="card", failure_reason="issuer_decline", incident_flag=False, payment_link=None)
        with patch("backend.chimera_messaging.twilio_provider.urlopen", return_value=FakeResponse()) as transport:
            result = provider.send_message(context, "synthetic message", "k" * 64)
        self.assertEqual(result.provider_message_id, "SM-gate11")
        self.assertEqual(provider.mode, "TEST")
        transport.assert_called_once()


if __name__ == "__main__":
    unittest.main()
