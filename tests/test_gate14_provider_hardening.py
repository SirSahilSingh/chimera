from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.models import PaymentEvent
from backend.app.main import create_app
from backend.chimera_payments.context import PaymentContext
from backend.chimera_payments.provider import PaymentProvider
from backend.chimera_payments.providers.razorpay import RazorpayPaymentProvider
from backend.chimera_payments.schemas import PaymentDemoScenario
from backend.provider_modes import mode_label


class Gate14ProviderHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("sqlite+pysqlite:///:memory:")
        self.client = TestClient(self.app)

    def test_demo_runs_all_supported_scenarios_through_stored_action(self) -> None:
        expected = {
            "payment_recovery": ("PAYMENT_LINK", "PAID"),
            "technical_retry": ("RETRY_LATER", "READY"),
            "voice_recovery": ("VOICE_RECOVERY", "PAID"),
            "escalation": ("ESCALATE", "OPEN"),
        }
        for scenario, (action, status) in expected.items():
            response = self.client.post("/api/v1/demo/run", json={"scenario": scenario, "provider_mode": "LOCAL"})
            self.assertEqual(response.status_code, 201, response.text)
            body = response.json()
            self.assertEqual((body["selected_action"], body["current_status"]), (action, status))
            self.assertTrue(body["journey_url"].endswith(f"/recovery-cases/{body['case_id']}/journey"))
            self.assertIn(body["provider_mode_label"], {"Demo Provider Execution", "Demo Voice Agent"})

    def test_demo_rejects_non_local_mode_without_calling_provider(self) -> None:
        response = self.client.post("/api/v1/demo/run", json={"scenario": "payment_recovery", "provider_mode": "LIVE"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "demo_requires_local_provider_mode")

    def test_payment_terminal_state_is_not_overwritten_by_late_event(self) -> None:
        result = self.client.post("/api/v1/demo/run", json={"scenario": "payment_recovery", "provider_mode": "LOCAL"})
        self.assertEqual(result.status_code, 201, result.text)
        journey = self.client.get(result.json()["journey_url"])
        payment_id = journey.json()["payments"][0]["id"]
        payment = self.client.get(f"/api/v1/payments/{payment_id}").json()
        provider = self.app.state.payment_provider
        pending = provider.demo_event(payment["provider_payment_link_id"], PaymentDemoScenario.PAYMENT_PENDING)
        pending = pending.model_copy(update={"provider_event_id": pending.provider_event_id + "-late"})
        raw = pending.model_dump_json().encode()
        response = self.client.post("/api/v1/payments/webhook/local", content=raw, headers={"x-payment-signature": provider.sign(pending)})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "PAID")
        session = self.app.state.session_factory()
        try:
            event = session.scalar(select(PaymentEvent).where(PaymentEvent.provider_event_id == pending.provider_event_id))
            self.assertEqual(event.payload_json["processing_result"], "ignored_terminal_state")
        finally:
            session.close()

    def test_razorpay_missing_credentials_is_safe_and_integer_based(self) -> None:
        provider = RazorpayPaymentProvider(None, None, None, enabled=True, mode="TEST")
        context = PaymentContext(recovery_case_id="c", intervention_id="i", decision_id="d", amount_paise=12500, currency="INR", description="synthetic", idempotency_key="k" * 64)
        with self.assertRaisesRegex(Exception, "provider_not_configured"):
            provider.create_payment_link(context)
        self.assertEqual(provider.mode, "TEST")
        self.assertNotIn("secret", json.dumps(context.model_dump()).lower())

    def test_mode_labels_are_controlled(self) -> None:
        self.assertEqual(mode_label("LOCAL", "voice"), "Demo Voice Agent")
        self.assertEqual(mode_label("MOCK"), "Simulated Payment Provider")
        self.assertEqual(mode_label("TEST"), "Provider Test Mode")
        self.assertEqual(mode_label("LIVE"), "Live Provider Execution")


if __name__ == "__main__":
    unittest.main()
