from __future__ import annotations

import json
import base64
import io
import unittest
import wave
from unittest.mock import patch
from urllib.parse import parse_qsl
from urllib.error import HTTPError

from backend.chimera_messaging.context import MessagingContext
from backend.chimera_messaging.twilio_provider import TwilioMessagingProvider
from backend.chimera_messaging.whatsapp_provider import WhatsAppMessagingProvider
from backend.chimera_orchestration.telegram_provider import TelegramEscalationProvider
from backend.chimera_payments.providers.razorpay import RazorpayPaymentProvider
from backend.chimera_payments.schemas import PaymentStatus
from backend.chimera_voice.sarvam_provider import SarvamSpeechError, SarvamSpeechProvider


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode("utf-8")
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class FreeDemoIntegrationTests(unittest.TestCase):
    def test_twilio_whatsapp_can_send_freeform_in_active_sandbox_window(self):
        provider = TwilioMessagingProvider(
            "AC123",
            "auth-token",
            "whatsapp:+14155238886",
            "whatsapp:+919999999999",
            enabled=True,
            whatsapp=True,
            mode="TEST",
        )
        context = MessagingContext(intervention_id="i", recovery_case_id="c", decision_id="d", selected_action="SEND_MESSAGE", customer_id="customer", customer_phone="+919999999999", language="en", amount_paise=12500, currency="INR", payment_method="card", failure_reason="issuer_decline", incident_flag=False)

        class FakeTwilioResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"sid":"SM-freeform"}'

        with patch("backend.chimera_messaging.twilio_provider.urlopen", return_value=FakeTwilioResponse()) as transport:
            result = provider.send_message(context, "Payment link: https://example.test", "k" * 64)
        self.assertEqual(result.provider_message_id, "SM-freeform")
        sent = dict(parse_qsl(transport.call_args.args[0].data.decode("utf-8"), keep_blank_values=True))
        self.assertEqual(sent["Body"], "Payment link: https://example.test")
        self.assertNotIn("ContentSid", sent)

    def test_twilio_http_failure_preserves_safe_provider_code_and_reason(self):
        provider = TwilioMessagingProvider(
            "AC123",
            "auth-token",
            "whatsapp:+14155238886",
            "whatsapp:+919999999999",
            enabled=True,
            whatsapp=True,
            content_sid="HX-template",
            mode="TEST",
        )
        context = MessagingContext(intervention_id="i", recovery_case_id="c", decision_id="d", selected_action="SEND_MESSAGE", customer_id="customer", customer_phone="+919999999999", language="en", amount_paise=12500, currency="INR", payment_method="card", failure_reason="issuer_decline", incident_flag=False)
        error = HTTPError(
            "https://api.twilio.com",
            400,
            "Bad Request",
            {},
            io.BytesIO(b'{"code":63016,"message":"A template is required for this message"}'),
        )

        with patch("backend.chimera_messaging.twilio_provider.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "twilio_63016") as raised:
                provider.send_message(context, "Payment link: https://example.test", "k" * 64)
        self.assertEqual(raised.exception.message, "A template is required for this message")

    def test_razorpay_webhook_extracts_customer_contact(self):
        payload = {
            "event": "payment.failed",
            "created_at": 1760000000,
            "payload": {
                "payment_link": {"entity": {"id": "plink_1", "amount": 12500, "currency": "INR"}},
                "payment": {"entity": {"id": "pay_1", "amount": 12500, "currency": "INR", "contact": "+919999999999", "email": "buyer@example.com"}},
            },
        }
        event = RazorpayPaymentProvider("key", "secret", "webhook", enabled=True).parse_webhook(json.dumps(payload).encode())
        self.assertEqual(event.status, PaymentStatus.FAILED)
        self.assertEqual(event.customer_phone, "+919999999999")
        self.assertEqual(event.customer_email, "buyer@example.com")

    def test_whatsapp_cloud_api_sends_to_case_contact(self):
        provider = WhatsAppMessagingProvider("token", "12345", None, "verify", "app-secret", enabled=True, mode="TEST")
        context = MessagingContext(intervention_id="i", recovery_case_id="c", decision_id="d", selected_action="SEND_MESSAGE", customer_id="customer", customer_phone="+919999999999", language="en", amount_paise=12500, currency="INR", payment_method="card", failure_reason="issuer_decline", incident_flag=False)
        with patch("backend.chimera_messaging.whatsapp_provider.urlopen", return_value=FakeResponse({"messages": [{"id": "wamid.1"}]})) as transport:
            result = provider.send_message(context, "Please pay https://example.test", "a" * 64)
        self.assertEqual(result.provider_message_id, "wamid.1")
        sent = json.loads(transport.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent["to"], "+919999999999")
        self.assertEqual(sent["type"], "text")

    def test_telegram_escalation_adapter_posts_operator_notification(self):
        provider = TelegramEscalationProvider("bot-token", "chat-id", enabled=True, mode="TEST")
        escalation = type("Escalation", (), {"priority": 1, "recovery_case_id": "case-1", "context_json": {"customer_id": "customer-1", "amount_paise": 1000}})()
        with patch("backend.chimera_orchestration.telegram_provider.urlopen", return_value=FakeResponse({"ok": True, "result": {"message_id": 7}})):
            result = provider.notify(escalation, "manual review required")
        self.assertEqual(result.provider, "telegram")
        self.assertEqual(result.provider_reference, "7")

    def test_sarvam_saaras_transcribes_code_mixed_audio(self):
        provider = SarvamSpeechProvider("sarvam-key", enabled=True)
        with patch("backend.chimera_voice.sarvam_provider.urlopen", return_value=FakeResponse({"transcript": "Haan, payment link bhej do"})) as transport:
            transcript = provider.transcribe(b"wav-audio")
        self.assertEqual(transcript, "Haan, payment link bhej do")
        request = transport.call_args.args[0]
        self.assertEqual(request.headers["Api-subscription-key"], "sarvam-key")
        body = request.data.decode("utf-8", errors="ignore")
        self.assertIn("saaras:v3", body)
        self.assertIn("codemix", body)
        self.assertIn("hi-IN", body)

    def test_sarvam_bulbul_returns_telephony_wav(self):
        audio = b"\x00\x01" * 160
        provider = SarvamSpeechProvider("sarvam-key", enabled=True)
        payload = {"audios": [base64.b64encode(audio).decode("ascii")]}
        with patch("backend.chimera_voice.sarvam_provider.urlopen", return_value=FakeResponse(payload)) as transport:
            result = provider.synthesize("नमस्ते, payment link ready है।")
        self.assertTrue(result.startswith(b"RIFF"))
        with wave.open(io.BytesIO(result), "rb") as decoded:
            self.assertEqual(decoded.getnchannels(), 1)
            self.assertEqual(decoded.getsampwidth(), 2)
            self.assertEqual(decoded.getframerate(), 8000)
        request = transport.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "bulbul:v3")
        self.assertEqual(body["language_code"], "hi-IN")
        self.assertEqual(body["speech_sample_rate"], 8000)
        self.assertEqual(body["output_audio_codec"], "linear16")

    def test_sarvam_credit_error_is_preserved_for_voice_diagnostics(self):
        provider = SarvamSpeechProvider("sarvam-key", enabled=True)
        error = HTTPError(
            "https://api.sarvam.ai/text-to-speech",
            402,
            "payment required",
            {},
            io.BytesIO(b'{"error":{"code":"insufficient_quota_error","message":"No credits available"}}'),
        )
        with patch("backend.chimera_voice.sarvam_provider.urlopen", side_effect=error):
            with self.assertRaises(SarvamSpeechError) as raised:
                provider.synthesize("Namaste")
        self.assertEqual(raised.exception.code, "sarvam_credits_exhausted")
        self.assertEqual(raised.exception.message, "No credits available")

    def test_twilio_whatsapp_uses_sandbox_addressing_and_template(self):
        provider = TwilioMessagingProvider(
            "AC123",
            "auth-token",
            "whatsapp:+14155238886",
            "whatsapp:+919999999999",
            enabled=True,
            whatsapp=True,
            content_sid="HX-template",
            status_callback_url="https://chimera.example/api/v1/messaging/webhook/twilio",
            mode="TEST",
        )
        context = MessagingContext(intervention_id="i", recovery_case_id="c", decision_id="d", selected_action="SEND_MESSAGE", customer_id="customer", customer_phone="+919999999999", language="en", amount_paise=12500, currency="INR", payment_method="card", failure_reason="issuer_decline", incident_flag=False)

        class FakeTwilioResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"sid":"SM-whatsapp"}'

        with patch("backend.chimera_messaging.twilio_provider.urlopen", return_value=FakeTwilioResponse()) as transport:
            result = provider.send_message(context, "Payment link: https://example.test", "k" * 64)
        self.assertEqual(result.provider_message_id, "SM-whatsapp")
        sent = dict(parse_qsl(transport.call_args.args[0].data.decode("utf-8"), keep_blank_values=True))
        self.assertEqual(sent["From"], "whatsapp:+14155238886")
        self.assertEqual(sent["To"], "whatsapp:+919999999999")
        self.assertEqual(sent["ContentSid"], "HX-template")
        self.assertEqual(json.loads(sent["ContentVariables"])["1"], "Payment link: https://example.test")
        self.assertEqual(sent["StatusCallback"], "https://chimera.example/api/v1/messaging/webhook/twilio")


if __name__ == "__main__":
    unittest.main()
