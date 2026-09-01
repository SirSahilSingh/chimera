from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from backend.app.db.models import Decision, RecoveryCase, VoiceEvent, VoiceTurn
from backend.app.main import create_app
from backend.chimera_voice.agent import VoiceAgent
from backend.chimera_voice.context import build_voice_context
from backend.chimera_voice.provider import LocalDeterministicVoiceProvider, LiveHttpVoiceProvider, VoiceProviderError, sign_webhook_event
from backend.chimera_voice.schemas import ConversationTurn, VoiceContext, VoiceIntent, VoiceScenario, VoiceWebhookEvent
from backend.chimera_voice.service import VoiceService
from backend.chimera_voice.state_machine import VoiceCallStatus, VoiceLifecycleError, VoiceTerminalStateError, validate_voice_transition
from backend.chimera_voice.validation import VoiceValidationError, validate_turn


class VoiceAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("sqlite+pysqlite:///:memory:")
        self.client = TestClient(self.app)

    def make_decision(self, action: str = "VOICE_RECOVERY", suffix: str = "1", customer_phone: str | None = None) -> str:
        session = self.app.state.session_factory()
        case = RecoveryCase(
            external_event_id=f"voice-event-{suffix}", payment_id=f"voice-payment-{suffix}",
            customer_id=f"synthetic-voice-{suffix}", amount_paise=12500, currency="INR",
            failure_reason="issuer_decline", incident_flag=False, payment_method="card",
            customer_phone=customer_phone,
            decision_timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc), status="DECIDED",
        )
        session.add(case)
        session.flush()
        decision = Decision(
            recovery_case_id=case.id, decision_run_id=f"voice-run-{suffix}", selected_action=action,
            predicted_probability=0.5, expected_gross_recovery_paise=6250, expected_net_value_paise=5000,
            model_version="test", feature_schema_version="test", engine_version="test",
            decision_timestamp=case.decision_timestamp, trace_json={},
        )
        session.add(decision)
        session.commit()
        decision_id = decision.id
        session.close()
        return decision_id

    def make_intervention(self, action: str = "VOICE_RECOVERY", suffix: str = "1", customer_phone: str | None = None) -> dict:
        decision_id = self.make_decision(action, suffix, customer_phone)
        response = self.client.post(f"/api/v1/decisions/{decision_id}/interventions")
        self.assertEqual(response.status_code, 201, response.text)
        intervention = response.json()
        if action != "DO_NOTHING":
            queued = self.client.post(f"/api/v1/interventions/{intervention['id']}/queue")
            self.assertEqual(queued.status_code, 200, queued.text)
        return intervention

    def test_voice_only_works_for_voice_recovery_and_keeps_decision_action(self) -> None:
        intervention = self.make_intervention("PAYMENT_LINK", "wrong-action")
        response = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/start")
        self.assertEqual(response.status_code, 409)
        voice = self.make_intervention("VOICE_RECOVERY", "correct-action")
        started = self.client.post(f"/api/v1/interventions/{voice['id']}/voice/start")
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(self.client.get(f"/api/v1/interventions/{voice['id']}").json()["action"], "VOICE_RECOVERY")

    def test_manual_call_can_accompany_payment_link_without_changing_decision(self) -> None:
        intervention = self.make_intervention("PAYMENT_LINK", "manual-call", customer_phone="+919999999999")

        response = self.client.post(f"/api/v1/recovery-cases/{intervention['recovery_case_id']}/voice/call")

        self.assertEqual(response.status_code, 200, response.text)
        call = response.json()
        self.assertEqual(call["intervention_id"], intervention["id"])
        self.assertEqual(call["provider"], "local")
        self.assertEqual(
            self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["action"],
            "PAYMENT_LINK",
        )
        session = self.app.state.session_factory()
        try:
            event_types = list(session.scalars(select(VoiceEvent.event_type).where(VoiceEvent.call_id == call["id"])))
            self.assertIn("MANUAL_CALL_REQUESTED", event_types)
        finally:
            session.close()

    def test_context_rejects_hidden_future_and_model_fields(self) -> None:
        context = VoiceContext(
            intervention_id="int", recovery_case_id="case", decision_id="decision", selected_action="VOICE_RECOVERY",
            payment_amount_paise=12500, currency="INR", failure_reason="issuer_decline", payment_method="card",
            incident_flag=False, allowed_recovery_options=("PAY_NOW",),
        )
        value = context.model_dump()
        for forbidden in ("customer_segment", "environment_state", "natural_recovery_probability", "future_outcome", "model_coefficients"):
            candidate = dict(value)
            candidate[forbidden] = "forbidden"
            with self.assertRaises(ValidationError):
                VoiceContext.model_validate(candidate)

    def test_allowed_intents_and_safe_unsupported_fallback(self) -> None:
        context = VoiceContext(
            intervention_id="int", recovery_case_id="case", decision_id="decision", selected_action="VOICE_RECOVERY",
            payment_amount_paise=12500, currency="INR", failure_reason="issuer_decline", payment_method="card",
            incident_flag=False, allowed_recovery_options=("PAY_NOW", "SEND_PAYMENT_LINK", "RETRY_LATER"),
        )
        agent = VoiceAgent(context)
        self.assertEqual(agent.classify_customer_text("Please send me a payment link"), VoiceIntent.SEND_PAYMENT_LINK)
        self.assertEqual(agent.classify_customer_text("I already paid"), VoiceIntent.ALREADY_PAID)
        self.assertEqual(agent.classify_customer_text("What happened?"), VoiceIntent.QUESTION)
        self.assertEqual(agent.classify_customer_text("Haan, payment link WhatsApp par bhej do"), VoiceIntent.SEND_PAYMENT_LINK)
        self.assertEqual(agent.classify_customer_text("Maine payment kar diya hai"), VoiceIntent.ALREADY_PAID)
        self.assertEqual(agent.classify_customer_text("Baad mein try karunga"), VoiceIntent.RETRY_LATER)
        self.assertEqual(agent.classify_customer_text("Haan ji, abhi pay kar dunga"), VoiceIntent.PAY_NOW)
        fallback = agent.response_turn(VoiceIntent.UNKNOWN, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertIn("incorrect information", fallback.text)

    def test_invalid_turn_mapping_and_unapproved_agent_number_are_rejected(self) -> None:
        context = VoiceContext(
            intervention_id="int", recovery_case_id="case", decision_id="decision", selected_action="VOICE_RECOVERY",
            payment_amount_paise=12500, currency="INR", failure_reason="issuer_decline", payment_method="card",
            incident_flag=False, allowed_recovery_options=("SEND_PAYMENT_LINK",),
        )
        invalid_mapping = ConversationTurn(
            speaker="customer", text="send a link", intent=VoiceIntent.SEND_PAYMENT_LINK, confidence=1.0,
            requested_action="RETRY_LATER", requires_confirmation=True, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), validated=True,
        )
        with self.assertRaises(VoiceValidationError):
            validate_turn(invalid_mapping, context)
        invalid_number = ConversationTurn(
            speaker="agent", text="Your payment is INR 9999.", intent=None, confidence=1.0,
            requested_action=None, requires_confirmation=False, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), validated=True,
        )
        with self.assertRaises(VoiceValidationError):
            validate_turn(invalid_number, context)

    def test_local_provider_is_deterministic_and_live_missing_config_is_safe(self) -> None:
        context = VoiceContext(
            intervention_id="int", recovery_case_id="case", decision_id="decision", selected_action="VOICE_RECOVERY",
            payment_amount_paise=12500, currency="INR", failure_reason="issuer_decline", payment_method="card",
            incident_flag=False, allowed_recovery_options=("PAY_NOW",),
        )
        provider = LocalDeterministicVoiceProvider()
        first = provider.start_call(context, idempotency_key="key", scenario=VoiceScenario.CUSTOMER_AGREES_TO_PAY)
        second = provider.start_call(context, idempotency_key="key", scenario=VoiceScenario.CUSTOMER_AGREES_TO_PAY)
        self.assertEqual(first, second)
        live = LiveHttpVoiceProvider(enabled=False, base_url=None, api_key=None, agent_id=None, phone_number=None, timeout_seconds=1)
        with self.assertRaisesRegex(VoiceProviderError, "voice_disabled"):
            live.start_call(context, idempotency_key="key", scenario=VoiceScenario.CUSTOMER_AGREES_TO_PAY)
        configured = LiveHttpVoiceProvider(enabled=True, base_url="https://voice.example", api_key="key", agent_id="agent", phone_number="+910000000000", timeout_seconds=1)
        with patch("backend.chimera_voice.provider.urlopen", side_effect=TimeoutError):
            with self.assertRaisesRegex(VoiceProviderError, "provider_timeout"):
                configured.start_call(context, idempotency_key="key", scenario=VoiceScenario.CUSTOMER_AGREES_TO_PAY)
        with self.assertRaisesRegex(VoiceProviderError, "provider_failure"):
            provider.start_call(context, idempotency_key="key", scenario=VoiceScenario.PROVIDER_FAILURE)

    def test_full_local_demo_scenarios_and_idempotency(self) -> None:
        scenarios = (
            (VoiceScenario.CUSTOMER_AGREES_TO_PAY, "PAY_NOW", "AWAITING_OUTCOME"),
            (VoiceScenario.CUSTOMER_REQUESTS_PAYMENT_LINK, "SEND_PAYMENT_LINK", "AWAITING_OUTCOME"),
            (VoiceScenario.CUSTOMER_REQUESTS_RETRY_LATER, "RETRY_LATER", "AWAITING_OUTCOME"),
            (VoiceScenario.CUSTOMER_ALREADY_PAID, "ALREADY_PAID", "AWAITING_OUTCOME"),
            (VoiceScenario.CUSTOMER_DECLINES, "DECLINE", "FAILED"),
            (VoiceScenario.NO_ANSWER, None, "AWAITING_OUTCOME"),
            (VoiceScenario.PROVIDER_FAILURE, None, "AWAITING_OUTCOME"),
        )
        for index, (scenario, intent, intervention_status) in enumerate(scenarios):
            intervention = self.make_intervention("VOICE_RECOVERY", f"scenario-{index}")
            response = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/demo", json={"scenario": scenario.value})
            self.assertEqual(response.status_code, 200, response.text)
            call = response.json()
            self.assertEqual(call["status"], "NO_ANSWER" if scenario == VoiceScenario.NO_ANSWER else "FAILED" if scenario == VoiceScenario.PROVIDER_FAILURE else "DECLINED" if scenario == VoiceScenario.CUSTOMER_DECLINES else "COMPLETED")
            self.assertEqual(call["outcome_intent"], intent)
            if scenario == VoiceScenario.CUSTOMER_REQUESTS_PAYMENT_LINK:
                self.assertTrue(call["payment_link"].startswith("https://demo.chimera.local/payment/"))
            self.assertEqual(self.client.get(f"/api/v1/interventions/{intervention['id']}").json()["status"], intervention_status)
            repeat = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/demo", json={"scenario": scenario.value})
            self.assertEqual(repeat.status_code, 200, repeat.text)
            self.assertEqual(repeat.json()["id"], call["id"])

    def test_voice_history_is_append_only_and_transcript_hash_is_reproducible(self) -> None:
        first = self.make_intervention("VOICE_RECOVERY", "hash-one")
        first_result = self.client.post(f"/api/v1/interventions/{first['id']}/voice/demo", json={"scenario": "customer_agrees_to_pay"}).json()
        self.assertEqual(len(first_result["turns"]), 3)
        self.assertGreaterEqual(len(first_result["events"]), 8)
        repeat = self.client.post(f"/api/v1/interventions/{first['id']}/voice/demo", json={"scenario": "customer_agrees_to_pay"}).json()
        self.assertEqual(first_result["transcript_hash"], repeat["transcript_hash"])
        history = self.client.get(f"/api/v1/interventions/{first['id']}/voice/history")
        self.assertEqual(len(history.json()["turns"]), 3)

    def test_webhook_signature_validation_and_duplicate_idempotency(self) -> None:
        intervention = self.make_intervention("VOICE_RECOVERY", "webhook")
        started = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/start").json()
        event = VoiceWebhookEvent(
            event_id="provider-event-1", provider_call_reference=started["provider_call_reference"], event_type="ringing",
            event_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), signature="placeholder",
        )
        signed = event.model_copy(update={"signature": sign_webhook_event(event)})
        first = self.client.post("/api/v1/voice/webhook/local", json=signed.model_dump(mode="json"))
        self.assertEqual(first.status_code, 200, first.text)
        duplicate = self.client.post("/api/v1/voice/webhook/local", json=signed.model_dump(mode="json"))
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        invalid = event.model_copy(update={"event_id": "provider-event-2", "signature": "invalid"})
        self.assertEqual(self.client.post("/api/v1/voice/webhook/local", json=invalid.model_dump(mode="json")).status_code, 409)

    def test_state_machine_and_persistence_do_not_allow_terminal_reentry(self) -> None:
        validate_voice_transition("CALL_QUEUED", VoiceCallStatus.CALL_INITIATED)
        validate_voice_transition("RINGING", VoiceCallStatus.CONNECTED)
        validate_voice_transition("CONVERSATION", VoiceCallStatus.AWAITING_RESOLUTION)
        with self.assertRaises(VoiceLifecycleError):
            validate_voice_transition("CALL_QUEUED", VoiceCallStatus.COMPLETED)
        with self.assertRaises(VoiceTerminalStateError):
            validate_voice_transition("COMPLETED", VoiceCallStatus.RINGING)

    def test_voice_rows_contain_no_credentials(self) -> None:
        intervention = self.make_intervention("VOICE_RECOVERY", "secrets")
        result = self.client.post(f"/api/v1/interventions/{intervention['id']}/voice/demo", json={"scenario": "customer_requests_payment_link"})
        text = result.text.lower()
        for secret in ("api_key", "authorization", "bearer", "secret"):
            self.assertNotIn(secret, text)
        session = self.app.state.session_factory()
        try:
            self.assertEqual(len(list(session.scalars(select(VoiceTurn).where(VoiceTurn.call_id == result.json()["id"])))), 3)
            self.assertGreater(len(list(session.scalars(select(VoiceEvent).where(VoiceEvent.call_id == result.json()["id"])))), 0)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
