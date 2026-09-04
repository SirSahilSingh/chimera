import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.chimera_voice.exotel_stream import ExotelStreamSession
from backend.chimera_voice.provider import ExotelVoiceProvider
from backend.chimera_voice.sarvam_provider import SarvamSpeechError, SarvamSpeechProvider


class ExotelVoiceAgentFixTests(unittest.TestCase):
    def setUp(self):
        self.exotel_provider = ExotelVoiceProvider(
            api_key="test-key",
            api_token="test-token",
            account_sid="test-account",
            flow_url="https://my.exotel.com/test-account/exoml/start_voice/123",
            caller_id="09888888888",
            api_base_url="https://api.in.exotel.com",
            public_base_url="https://chimera.example.com",
            webhook_secret=None,
            enabled=True,
            agentstream_enabled=False,
            stream_url="wss://chimera.example.com/api/v1/voice/exotel/stream",
            mode="TEST",
        )
        self.app = create_app("sqlite+pysqlite:///:memory:", voice_provider=self.exotel_provider)
        self.client = TestClient(self.app)

    def _setup_intervention(self):
        case = self.client.post(
            "/api/v1/recovery-cases",
            json={
                "external_event_id": "evt-fix-1",
                "payment_id": "pay-fix-1",
                "customer_id": "cust-fix-1",
                "customer_phone": "+919999999999",
                "amount_paise": 125000,
                "currency": "INR",
                "failure_reason": "insufficient_funds",
                "incident_flag": False,
                "payment_method": "card",
                "decision_timestamp": "2026-01-01T12:00:00+00:00",
            },
        ).json()
        decision = self.client.post(f"/api/v1/recovery-cases/{case['id']}/decide").json()
        intervention = self.client.post(f"/api/v1/decisions/{decision['id']}/interventions").json()
        self.client.post(f"/api/v1/interventions/{intervention['id']}/queue")
        return case, decision, intervention

    def test_exotel_stream_resolver_handles_get_with_pascal_case_callsid(self):
        case, decision, intervention = self._setup_intervention()
        with patch.object(self.exotel_provider, "start_call") as mock_start:
            mock_start.return_value = MagicMock(provider="exotel", provider_call_reference="exotel-call-sid-123")
            call_resp = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/start")
            self.assertEqual(call_resp.status_code, 200, call_resp.text)

        # Call the resolver with PascalCase CallSid (as Exotel sends)
        res = self.client.get("/api/v1/voice/exotel/stream-resolver?CallSid=exotel-call-sid-123")
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn("url", body)
        self.assertIn("intervention_id", body["url"])
        self.assertIn("websocket_url", body)

    def test_exotel_stream_resolver_handles_post_with_form_body(self):
        case, decision, intervention = self._setup_intervention()
        with patch.object(self.exotel_provider, "start_call") as mock_start:
            mock_start.return_value = MagicMock(provider="exotel", provider_call_reference="exotel-call-sid-456")
            call_resp = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/start")
            self.assertEqual(call_resp.status_code, 200, call_resp.text)

        # Call the resolver via POST with form-encoded CallSid
        res = self.client.post(
            "/api/v1/voice/exotel/stream-resolver",
            data={"CallSid": "exotel-call-sid-456"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn("url", body)
        self.assertIn(intervention["id"], body["url"])

    def test_exotel_stream_resolver_fallback_to_latest_active_call(self):
        case, decision, intervention = self._setup_intervention()
        with patch.object(self.exotel_provider, "start_call") as mock_start:
            mock_start.return_value = MagicMock(provider="exotel", provider_call_reference="exotel-call-sid-789")
            call_resp = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/start")
            self.assertEqual(call_resp.status_code, 200, call_resp.text)

        # Call the resolver without CallSid, should fallback to latest active call
        res = self.client.get("/api/v1/voice/exotel/stream-resolver")
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn("url", body)
        self.assertIn(intervention["id"], body["url"])

    def test_exotel_status_handles_pascal_case_and_json(self):
        case, decision, intervention = self._setup_intervention()
        with patch.object(self.exotel_provider, "start_call") as mock_start:
            mock_start.return_value = MagicMock(provider="exotel", provider_call_reference="exotel-call-sid-stat")
            call_resp = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/start")
            self.assertEqual(call_resp.status_code, 200, call_resp.text)

        # Send Exotel status update with PascalCase keys in JSON
        res = self.client.post(
            "/api/v1/voice/exotel/status",
            json={"CallSid": "exotel-call-sid-stat", "Status": "in-progress"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["status"], "CONNECTED")

    def test_exotel_stream_session_resolves_intervention_id_from_call_sid(self):
        async def run_test():
            websocket = AsyncMock()
            voice_service = MagicMock()
            speech_provider = MagicMock()

            mock_call = MagicMock()
            mock_call.intervention_id = "resolved-int-123"
            voice_service.get_call_for_provider_reference.return_value = mock_call
            voice_service.exotel_opening.return_value = "Hello"
            speech_provider.synthesize.return_value = ExotelStreamSession._wav(b"\x00\x01" * 1600)

            session = ExotelStreamSession(
                websocket,
                voice_service=voice_service,
                speech_provider=speech_provider,
                intervention_id=None,  # Not provided in URL
            )

            start_event = {
                "event": "start",
                "stream_sid": "stream-sid-1",
                "start": {
                    "stream_sid": "stream-sid-1",
                    "call_sid": "exotel-call-sid-999",
                    "custom_parameters": {},
                },
            }

            await session._handle_start(start_event)
            self.assertEqual(session.intervention_id, "resolved-int-123")
            voice_service.get_call_for_provider_reference.assert_called_once_with("exotel-call-sid-999")
            speech_provider.synthesize.assert_called_once_with("Hello")
            self.assertTrue(websocket.send_json.called)

        asyncio.run(run_test())

    def test_sarvam_provider_auto_enables_with_api_key(self):
        provider = SarvamSpeechProvider("sarvam-test-key")
        self.assertTrue(provider.enabled)

    def test_sarvam_provider_synthesize_handles_both_audios_and_audio_keys(self):
        provider = SarvamSpeechProvider("sarvam-test-key", enabled=True)
        with patch.object(provider, "_request", return_value={"audio": "AAECAwQFBgc="}):
            pcm_bytes = provider.synthesize("test")
            self.assertTrue(pcm_bytes.startswith(b"RIFF"))


if __name__ == "__main__":
    unittest.main()
