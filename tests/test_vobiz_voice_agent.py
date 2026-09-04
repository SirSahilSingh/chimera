import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.chimera_voice.groq_provider import GroqVoiceAgent
from backend.chimera_voice.schemas import VoiceContext
from backend.chimera_voice.vobiz_provider import VobizVoiceProvider


class VobizVoiceAgentTests(unittest.TestCase):
    def setUp(self):
        self.vobiz_provider = VobizVoiceProvider(
            auth_id="vobiz-test-auth-id",
            auth_token="vobiz-test-auth-token",
            caller_id="+919876543210",
            public_base_url="https://chimera.onrender.com",
            api_base_url="https://api.vobiz.ai",
            enabled=True,
            mode="TEST",
        )
        self.app = create_app("sqlite+pysqlite:///:memory:", voice_provider=self.vobiz_provider)
        self.client = TestClient(self.app)

    def _setup_intervention(self):
        case = self.client.post(
            "/api/v1/recovery-cases",
            json={
                "external_event_id": "evt-vobiz-1",
                "payment_id": "pay-vobiz-1",
                "customer_id": "cust-vobiz-1",
                "customer_phone": "+919111122222",
                "amount_paise": 149900,
                "currency": "INR",
                "failure_reason": "insufficient_funds",
                "incident_flag": False,
                "payment_method": "upi",
                "decision_timestamp": "2026-01-01T12:00:00+00:00",
            },
        ).json()
        decision = self.client.post(f"/api/v1/recovery-cases/{case['id']}/decide").json()
        intervention = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions").json()
        self.client.post(f"/api/v1/interventions/{intervention['id']}/queue")
        return case, decision, intervention

    def test_vobiz_answer_xml_generation(self):
        case, decision, intervention = self._setup_intervention()
        resp = self.client.get(f"/api/v1/voice/vobiz/answer?intervention_id={intervention['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/xml", resp.headers["content-type"])
        self.assertIn("<Stream bidirectional=\"true\"", resp.text)
        self.assertIn("audio/x-l16;rate=16000", resp.text)
        self.assertIn(f"intervention_id={intervention['id']}", resp.text)

    def test_vobiz_start_call_request(self):
        case, decision, intervention = self._setup_intervention()
        with patch("backend.chimera_voice.vobiz_provider.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"call_uuid": "vobiz-call-uuid-999"}).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            start_resp = self.client.post(
                "/api/v1/voice/outbound/call",
                json={"intervention_id": intervention["id"], "customer_phone": "+919876543210"},
            )
            self.assertEqual(start_resp.status_code, 200, start_resp.text)
            self.assertEqual(start_resp.json()["provider"], "vobiz")
            self.assertEqual(start_resp.json()["provider_call_reference"], "vobiz-call-uuid-999")

    def test_groq_agent_prompt_grounding(self):
        agent = GroqVoiceAgent(api_key="gsk-mock-key")
        context = VoiceContext(
            intervention_id="int-1",
            recovery_case_id="case-1",
            decision_id="dec-1",
            customer_phone="+919876543210",
            selected_action="VOICE_RECOVERY",
            payment_amount_paise=149900,
            currency="INR",
            failure_reason="insufficient_funds",
            payment_method="upi",
            incident_flag=False,
            allowed_recovery_options=("PAY_NOW", "SEND_PAYMENT_LINK"),
        )
        prompt = agent._build_system_prompt(context)
        self.assertIn("₹1,499.00 INR", prompt)
        self.assertIn("insufficient_funds", prompt)
        self.assertIn("Hinglish", prompt)
        self.assertIn("NEVER ask for card numbers", prompt)

    def test_vobiz_hangup_callback_completes_call(self):
        case, decision, intervention = self._setup_intervention()
        with patch("backend.chimera_voice.vobiz_provider.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"call_uuid": "vobiz-call-uuid-888"}).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            start_resp = self.client.post(
                "/api/v1/voice/outbound/call",
                json={"intervention_id": intervention["id"], "customer_phone": "+919876543210"},
            )
            self.assertEqual(start_resp.status_code, 200)

        # Send hangup webhook
        hangup_resp = self.client.post(
            f"/api/v1/voice/vobiz/hangup?intervention_id={intervention['id']}",
            json={"CallUUID": "vobiz-call-uuid-888", "HangupCause": "NORMAL_CLEARING"},
        )
        self.assertEqual(hangup_resp.status_code, 200)
        self.assertEqual(hangup_resp.text, "OK")

        # Verify call transitioned to COMPLETED in history
        history_resp = self.client.get(f"/api/v1/interventions/{intervention['id']}/voice/history")
        self.assertEqual(history_resp.status_code, 200)
        history = history_resp.json()
        self.assertEqual(history["call"]["status"], "COMPLETED")
        self.assertIsNotNone(history["call"]["completed_at"])
