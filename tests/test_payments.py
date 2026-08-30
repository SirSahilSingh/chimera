from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.db.models import Decision, PaymentEvent, PaymentLink, RecoveryCase
from backend.app.main import create_app
from backend.chimera_payments.context import PaymentContext
from backend.chimera_payments.errors import PaymentAuthorityError, PaymentValidationError, PaymentWebhookError
from backend.chimera_payments.providers.local import LocalDeterministicPaymentProvider
from backend.chimera_payments.providers.razorpay import RazorpayPaymentProvider
from backend.chimera_payments.schemas import PaymentDemoScenario, PaymentWebhookEvent
from backend.chimera_payments.service import PaymentService


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class PaymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("sqlite+pysqlite:///:memory:")
        self.client = TestClient(self.app)

    def make_intervention(self, action: str, suffix: str = "1") -> dict:
        session = self.app.state.session_factory()
        case = RecoveryCase(external_event_id=f"pay-event-{suffix}", payment_id=f"pay-{suffix}", customer_id=f"synthetic-{suffix}", amount_paise=12500, currency="INR", failure_reason="issuer_decline", incident_flag=False, payment_method="card", decision_timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc), status="DECIDED")
        session.add(case)
        session.flush()
        decision = Decision(recovery_case_id=case.id, decision_run_id=f"pay-run-{suffix}", selected_action=action, predicted_probability=0.5, expected_gross_recovery_paise=6250, expected_net_value_paise=5000, model_version="test", feature_schema_version="test", engine_version="test", decision_timestamp=case.decision_timestamp, trace_json={})
        session.add(decision)
        session.commit()
        decision_id = decision.id
        session.close()
        intervention = self.client.post(f"/api/v1/decisions/{decision_id}/interventions")
        self.assertEqual(intervention.status_code, 201, intervention.text)
        queued = self.client.post(f"/api/v1/interventions/{intervention.json()['id']}/queue")
        self.assertEqual(queued.status_code, 200, queued.text)
        return queued.json()

    def create_link(self, action: str = "PAYMENT_LINK", suffix: str = "link") -> tuple[dict, dict]:
        intervention = self.make_intervention(action, suffix)
        if action == "PAYMENT_LINK":
            response = self.client.post(f"/api/v1/interventions/{intervention['id']}/payment-link")
        else:
            service = PaymentService(self.app.state.session_factory(), self.app.state.payment_provider)
            link = service.create_for_voice_intent(intervention["id"], "SEND_PAYMENT_LINK")
            response = self.client.get(f"/api/v1/payments/{link.id}")
        self.assertEqual(response.status_code, 201 if action == "PAYMENT_LINK" else 200, response.text)
        return intervention, response.json()

    def test_context_is_strict_and_integer_only(self):
        with self.assertRaises(ValidationError):
            PaymentContext(recovery_case_id="c", intervention_id="i", decision_id="d", amount_paise=1.5, currency="INR", description="x", idempotency_key="a" * 64)
        valid = PaymentContext(recovery_case_id="c", intervention_id="i", decision_id="d", amount_paise=1, currency="INR", description="x", idempotency_key="a" * 64)
        invalid = valid.model_dump()
        invalid["customer_segment"] = "LOW_ENGAGEMENT"
        with self.assertRaises(ValidationError):
            PaymentContext.model_validate(invalid)

    def test_authority_is_stored_action_based(self):
        intervention = self.make_intervention("SEND_MESSAGE", "wrong")
        response = self.client.post(f"/api/v1/interventions/{intervention['id']}/payment-link")
        self.assertEqual(response.status_code, 409)
        with self.assertRaises(PaymentAuthorityError):
            PaymentService(self.app.state.session_factory(), self.app.state.payment_provider).create_for_voice_intent(intervention["id"], "PAY_NOW")

    def test_success_confirms_recovery_and_is_idempotent(self):
        intervention, link = self.create_link(suffix="success")
        first = self.client.post(f"/api/v1/payments/{link['id']}/demo/complete", json={"scenario": "payment_success"})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "PAID")
        provider: LocalDeterministicPaymentProvider = self.app.state.payment_provider
        event = provider.demo_event(link["provider_payment_link_id"], PaymentDemoScenario.PAYMENT_SUCCESS)
        raw = event.model_dump_json().encode()
        duplicate = self.client.post("/api/v1/payments/webhook/local", content=raw, headers={"x-payment-signature": provider.sign(event)})
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["status"], "RECOVERED")
        session = self.app.state.session_factory()
        self.assertEqual(len(list(session.query(PaymentEvent))), 2)
        session.close()

    def test_pending_failed_expired_never_claim_recovery(self):
        for scenario, expected in (("payment_pending", "ACTIVE"), ("payment_failed", "FAILED"), ("payment_expired", "EXPIRED")):
            intervention, link = self.create_link(suffix=scenario)
            response = self.client.post(f"/api/v1/payments/{link['id']}/demo/complete", json={"scenario": scenario})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], expected)
            self.assertNotEqual(self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["status"], "RECOVERED")

    def test_out_of_order_events_do_not_revert_paid(self):
        intervention, link = self.create_link(suffix="order")
        response = self.client.post(f"/api/v1/payments/{link['id']}/demo/complete", json={"scenario": "out_of_order_event"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "PAID")
        self.assertEqual(self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["status"], "RECOVERED")

    def test_stale_event_cannot_turn_expired_link_into_paid(self):
        intervention, link = self.create_link(suffix="stale")
        expired = self.client.post(f"/api/v1/payments/{link['id']}/demo/complete", json={"scenario": "payment_expired"})
        self.assertEqual(expired.status_code, 200)
        provider: LocalDeterministicPaymentProvider = self.app.state.payment_provider
        event = provider.demo_event(link["provider_payment_link_id"], PaymentDemoScenario.PAYMENT_SUCCESS)
        raw = event.model_dump_json().encode()
        response = self.client.post("/api/v1/payments/webhook/local", content=raw, headers={"x-payment-signature": provider.sign(event)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "EXPIRED")
        self.assertEqual(self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["status"], "EXPIRED")

    def test_webhook_signature_and_amount_currency_validation(self):
        intervention, link = self.create_link(suffix="webhook")
        provider: LocalDeterministicPaymentProvider = self.app.state.payment_provider
        event = provider.demo_event(link["provider_payment_link_id"], PaymentDemoScenario.PAYMENT_SUCCESS)
        raw = event.model_dump_json().encode()
        bad = self.client.post("/api/v1/payments/webhook/local", content=raw, headers={"x-payment-signature": "bad"})
        self.assertEqual(bad.status_code, 409)
        invalid = event.model_copy(update={"amount_paise": 1, "provider_event_id": "wrong-amount"})
        invalid_raw = invalid.model_dump_json().encode()
        signature = provider.sign(invalid)
        response = self.client.post("/api/v1/payments/webhook/local", content=invalid_raw, headers={"x-payment-signature": signature})
        self.assertEqual(response.status_code, 409)
        self.assertNotEqual(self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["status"], "RECOVERED")

    def test_voice_validated_intent_uses_payment_service(self):
        intervention = self.make_intervention("VOICE_RECOVERY", "voice-link")
        response = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/demo", json={"scenario": "customer_requests_payment_link"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["payment_link"].startswith("https://demo.chimera.local/payment/"))
        session = self.app.state.session_factory()
        self.assertEqual(session.query(PaymentLink).filter_by(intervention_id=intervention["id"]).count(), 1)
        session.close()

    def test_local_provider_is_deterministic(self):
        provider = LocalDeterministicPaymentProvider()
        context = PaymentContext(recovery_case_id="c", intervention_id="i", decision_id="d", amount_paise=100, currency="INR", description="x", idempotency_key="b" * 64)
        first = provider.create_payment_link(context)
        second = provider.create_payment_link(context)
        self.assertEqual((first.provider_payment_link_id, first.short_url), (second.provider_payment_link_id, second.short_url))
        event = provider.demo_event(first.provider_payment_link_id, PaymentDemoScenario.PAYMENT_SUCCESS)
        self.assertEqual(provider.sign(event), provider.sign(event))

    def test_razorpay_adapter_uses_integer_payload_and_hmac(self):
        provider = RazorpayPaymentProvider("key", "secret", "webhook", enabled=True)
        context = PaymentContext(recovery_case_id="c", intervention_id="i", decision_id="d", amount_paise=12500, currency="INR", description="x", idempotency_key="c" * 64)
        with patch("backend.chimera_payments.providers.razorpay.urlopen", return_value=FakeResponse({"id": "plink_1", "short_url": "https://rzp.io/i/1", "status": "issued"})) as mocked:
            result = provider.create_payment_link(context)
        request = mocked.call_args.args[0]
        self.assertIn(b'"amount": 12500', request.data)
        self.assertLessEqual(len(json.loads(request.data)["reference_id"]), 40)
        self.assertTrue(json.loads(request.data)["reference_id"].startswith("chimera-"))
        self.assertNotIn(b"secret", request.data)
        with patch("backend.chimera_payments.providers.razorpay.urlopen", side_effect=[TimeoutError(), FakeResponse({"id": "plink_1", "short_url": "https://rzp.io/i/1", "status": "issued"})]) as retried:
            provider.create_payment_link(context)
        self.assertEqual(retried.call_count, 2)
        event = b'{"event":"test"}'
        signature = hmac.new(b"webhook", event, hashlib.sha256).hexdigest()
        self.assertTrue(provider.verify_webhook(event, signature))
        webhook = json.dumps({"event": "payment_link.paid", "created_at": 1767225600, "payload": {"payment_link": {"entity": {"id": "plink_1", "amount": 12500, "currency": "INR", "status": "paid"}}, "payment": {"entity": {"id": "pay_1"}}}}).encode()
        parsed = provider.parse_webhook(webhook, "rzp-event-1")
        self.assertEqual((parsed.provider_payment_link_id, parsed.provider_payment_id, parsed.status.value, parsed.amount_paise), ("plink_1", "pay_1", "PAID", 12500))


if __name__ == "__main__":
    unittest.main()
