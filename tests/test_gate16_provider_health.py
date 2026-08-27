from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.models import PaymentLink, ProviderVerification
from backend.app.main import create_app
from backend.chimera_payments.errors import PaymentProviderError


class Gate16ProviderHealthTests(unittest.TestCase):
    def test_local_readiness_is_explicit_and_verification_has_no_customer_side_effect(self) -> None:
        app = create_app("sqlite+pysqlite:///:memory:")
        client = TestClient(app)
        response = client.get("/api/v1/providers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["provider_name"] for row in response.json()}, {"voice", "razorpay", "twilio", "retry", "escalation"})
        self.assertTrue(all(row["readiness_status"] == "MOCK_VERIFIED" for row in response.json()))

        verified = client.post("/api/v1/providers/razorpay/verify", json={})
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertEqual(verified.json()["verification_result"], "SUCCESS")
        self.assertEqual(verified.json()["readiness_status"], "MOCK_VERIFIED")
        self.assertNotIn("chimera-local", verified.text)
        session = app.state.session_factory()
        self.assertEqual(len(list(session.scalars(select(PaymentLink)))), 0)
        self.assertEqual(len(list(session.scalars(select(ProviderVerification)))), 1)
        session.close()

    def test_missing_external_credentials_are_not_configured(self) -> None:
        with patch.dict(os.environ, {"PAYMENT_PROVIDER": "razorpay", "RAZORPAY_MODE": "TEST", "RAZORPAY_KEY_ID": "", "RAZORPAY_KEY_SECRET": ""}, clear=False):
            app = create_app("sqlite+pysqlite:///:memory:")
            client = TestClient(app)
            response = client.get("/api/v1/providers/razorpay")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["readiness_status"], "NOT_CONFIGURED")
            verified = client.post("/api/v1/providers/razorpay/verify", json={})
            self.assertEqual(verified.status_code, 200)
            self.assertEqual(verified.json()["error_type"], "missing_configuration")

    def test_live_is_configured_but_blocked_without_explicit_safety_switch(self) -> None:
        values = {"PAYMENT_PROVIDER": "razorpay", "RAZORPAY_MODE": "LIVE", "RAZORPAY_KEY_ID": "key-id", "RAZORPAY_KEY_SECRET": "key-secret", "RAZORPAY_WEBHOOK_SECRET": "webhook-secret", "CHIMERA_ALLOW_LIVE_EXECUTION": "false"}
        with patch.dict(os.environ, values, clear=False):
            app = create_app("sqlite+pysqlite:///:memory:")
            client = TestClient(app)
            response = client.post("/api/v1/providers/razorpay/verify", json={})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["provider_mode"], "LIVE")
            self.assertEqual(response.json()["readiness_status"], "CONFIGURED")
            self.assertEqual(response.json()["verification_result"], "SKIPPED_LIVE_DISABLED")
            self.assertEqual(response.json()["error_type"], "live_execution_disabled")
            self.assertNotIn("key-secret", response.text)

            blocked = client.post("/api/v1/providers/razorpay/test", json={"confirm": True})
            self.assertEqual(blocked.status_code, 200)
            self.assertEqual(blocked.json()["verification_result"], "SKIPPED_LIVE_DISABLED")

    def test_test_probe_status_requires_explicit_confirmation_and_is_append_only(self) -> None:
        values = {"PAYMENT_PROVIDER": "razorpay", "RAZORPAY_MODE": "TEST", "RAZORPAY_KEY_ID": "key-id", "RAZORPAY_KEY_SECRET": "key-secret", "RAZORPAY_WEBHOOK_SECRET": "webhook-secret", "CHIMERA_ALLOW_LIVE_EXECUTION": "false"}
        with patch.dict(os.environ, values, clear=False):
            app = create_app("sqlite+pysqlite:///:memory:")
            app.state.payment_provider.verify_connectivity = lambda: None
            client = TestClient(app)
            self.assertEqual(client.post("/api/v1/providers/razorpay/test", json={"confirm": False}).status_code, 422)
            first = client.post("/api/v1/providers/razorpay/test", json={"confirm": True})
            second = client.post("/api/v1/providers/razorpay/test", json={"confirm": True})
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(first.json()["readiness_status"], "TEST_VERIFIED")
            self.assertEqual(second.status_code, 200, second.text)
            self.assertNotEqual(first.json()["verification_id"], second.json()["verification_id"])
            session = app.state.session_factory()
            self.assertEqual(len(list(session.scalars(select(ProviderVerification)))), 2)
            session.close()

    def test_local_test_endpoint_rejects_mode_mismatch_without_execution(self) -> None:
        app = create_app("sqlite+pysqlite:///:memory:")
        client = TestClient(app)
        response = client.post("/api/v1/providers/voice/test", json={"confirm": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error_type"], "provider_mode_mismatch")
        self.assertEqual(response.json()["verification_result"], "FAILED")

    def test_probe_failures_are_controlled_and_redacted(self) -> None:
        values = {"PAYMENT_PROVIDER": "razorpay", "RAZORPAY_MODE": "TEST", "RAZORPAY_KEY_ID": "key-id", "RAZORPAY_KEY_SECRET": "key-secret"}
        with patch.dict(os.environ, values, clear=False):
            app = create_app("sqlite+pysqlite:///:memory:")
            def fail_probe() -> None:
                raise PaymentProviderError("invalid_credentials")
            app.state.payment_provider.verify_connectivity = fail_probe
            response = TestClient(app).post("/api/v1/providers/razorpay/test", json={"confirm": True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["readiness_status"], "FAILED")
            self.assertEqual(response.json()["error_type"], "invalid_credentials")
            self.assertNotIn("key-secret", response.text)


if __name__ == "__main__":
    unittest.main()
