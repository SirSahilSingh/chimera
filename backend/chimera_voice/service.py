from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.db.models import Intervention, RecoveryCase, VoiceCall, VoiceEvent, VoiceTurn
from backend.app.interventions.service import InterventionService
from backend.app.interventions.state_machine import InterventionStatus
from backend.app.schemas import InterventionOutcomeCreate
from backend.provider_modes import safe_failure_code

from .agent import VoiceAgent
from .context import build_voice_context, context_hash
from .errors import InvalidVoiceWebhookError, VoiceActionNotAllowedError, VoiceDuplicateError, VoiceNotFoundError, VoiceProviderFailure
from .provider import TwilioVoiceProvider, VoiceProvider, VoiceProviderError
from .sarvam_provider import SarvamSpeechError, SarvamSpeechProvider
from .schemas import ConversationTurn, VoiceContext, VoiceIntent, VoiceScenario, VoiceWebhookEvent
from .state_machine import TERMINAL_VOICE_STATUSES, VoiceCallStatus, validate_voice_transition
from .transcript import payload_hash, transcript_hash
from .versions import VOICE_AGENT_VERSION, VOICE_PROMPT_VERSION


class VoiceService:
    """Coordinates a voice call without decision or policy authority."""

    def __init__(self, session: Session, provider: VoiceProvider, intervention_service: InterventionService | None = None, payment_service=None, messaging_service=None, speech_provider: SarvamSpeechProvider | None = None) -> None:
        self.session = session
        self.provider = provider
        self.interventions = intervention_service or InterventionService(session)
        self.payment_service = payment_service
        self.messaging_service = messaging_service
        self.speech_provider = speech_provider

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def get_call(self, call_id: str) -> VoiceCall:
        result = self.session.execute(
            select(VoiceCall)
            .options(
                joinedload(VoiceCall.intervention).joinedload(Intervention.decision),
                joinedload(VoiceCall.intervention).joinedload(Intervention.recovery_case),
                selectinload(VoiceCall.turns),
                selectinload(VoiceCall.events),
            )
            .where(VoiceCall.id == call_id)
        )
        call = result.unique().scalar_one_or_none()
        if call is None:
            raise VoiceNotFoundError("voice call not found")
        return call

    def get_call_for_intervention(self, intervention_id: str) -> VoiceCall:
        call = self.session.scalar(
            select(VoiceCall)
            .options(
                joinedload(VoiceCall.intervention).joinedload(Intervention.decision),
                joinedload(VoiceCall.intervention).joinedload(Intervention.recovery_case),
                selectinload(VoiceCall.turns),
                selectinload(VoiceCall.events),
            )
            .where(VoiceCall.intervention_id == intervention_id)
        )
        if call is None:
            raise VoiceNotFoundError("voice call not found")
        return call

    def get_call_for_provider_reference(self, provider_call_reference: str) -> VoiceCall:
        call = self.session.scalar(
            select(VoiceCall)
            .options(
                joinedload(VoiceCall.intervention).joinedload(Intervention.decision),
                joinedload(VoiceCall.intervention).joinedload(Intervention.recovery_case),
                selectinload(VoiceCall.turns),
                selectinload(VoiceCall.events),
            )
            .where(VoiceCall.provider_call_reference == provider_call_reference)
        )
        if call is None:
            raise VoiceNotFoundError("voice call not found")
        return call

    def get_latest_active_call(self) -> VoiceCall | None:
        """Find the most recent in-flight voice call for session fallback."""
        active_statuses = (
            VoiceCallStatus.CALL_QUEUED.value,
            VoiceCallStatus.CALL_INITIATED.value,
            VoiceCallStatus.RINGING.value,
            VoiceCallStatus.CONNECTED.value,
            VoiceCallStatus.CONVERSATION.value,
            VoiceCallStatus.AWAITING_RESOLUTION.value,
        )
        return self.session.scalar(
            select(VoiceCall)
            .options(
                joinedload(VoiceCall.intervention).joinedload(Intervention.decision),
                joinedload(VoiceCall.intervention).joinedload(Intervention.recovery_case),
                selectinload(VoiceCall.turns),
                selectinload(VoiceCall.events),
            )
            .where(VoiceCall.status.in_(active_statuses))
            .order_by(VoiceCall.created_at.desc())
        )

    def start(self, intervention_id: str, scenario: VoiceScenario, *, allow_secondary: bool = False, source: str = "decision") -> tuple[VoiceCall, bool]:
        intervention = self.interventions.get_intervention(intervention_id)
        self._assert_voice_intervention(intervention, allow_secondary=allow_secondary)
        context = build_voice_context(intervention, allow_secondary=allow_secondary)
        existing = self.session.scalar(select(VoiceCall).where(VoiceCall.intervention_id == intervention_id))
        if existing is not None:
            if existing.status in TERMINAL_VOICE_STATUSES and source == "operator":
                # Operator retry: reset call for a fresh attempt
                key = self._idempotency_key(intervention_id, scenario, f"{self.provider.name}-{self._now().isoformat()}")
                existing.idempotency_key = key
                existing.status = VoiceCallStatus.CALL_QUEUED.value
                existing.provider = self.provider.name
                existing.provider_mode = self.provider.mode
                existing.failure_code = None
                existing.completed_at = None
                self.session.flush()
                try:
                    started = self.provider.start_call(context, idempotency_key=key, scenario=scenario)
                    existing.provider_call_reference = started.provider_call_reference
                    existing.provider = started.provider
                    existing.started_at = self._now()
                    self._transition(existing, VoiceCallStatus.CALL_INITIATED)
                    self._event(existing, "CALL_REINITIATED", "operator", {"provider": started.provider})
                    self.session.commit()
                    return self.get_call(existing.id), True
                except VoiceProviderError as exc:
                    existing.failure_code = safe_failure_code(exc.code)
                    existing.completed_at = self._now()
                    self._transition(existing, VoiceCallStatus.FAILED)
                    payload = {"failure_code": exc.code}
                    if exc.provider_code:
                        payload["failure_classification"] = exc.provider_code
                    if exc.reason:
                        payload["failure_reason"] = exc.reason
                    self._event(existing, "CALL_FAILED", "provider", payload)
                    self.session.commit()
                    raise VoiceProviderFailure(existing.failure_code) from None
            if existing.scenario != scenario.value:
                raise VoiceDuplicateError("intervention already has a voice call with a different scenario")
            return self.get_call(existing.id), False

        if intervention.status == InterventionStatus.READY.value:
            self.interventions.execute(intervention.id)
            intervention = self.interventions.get_intervention(intervention.id)
        if intervention.status != InterventionStatus.AWAITING_OUTCOME.value:
            raise VoiceActionNotAllowedError(f"voice call requires an executable intervention, got {intervention.status}")

        context = build_voice_context(intervention, allow_secondary=allow_secondary)
        key = self._idempotency_key(intervention.id, scenario, self.provider.name)
        call = VoiceCall(
            intervention_id=intervention.id,
            recovery_case_id=intervention.recovery_case_id,
            provider=self.provider.name,
            provider_mode=self.provider.mode,
            status=VoiceCallStatus.CALL_QUEUED.value,
            scenario=scenario.value,
            idempotency_key=key,
            input_hash=context_hash(context),
            transcript_hash=self._empty_transcript_hash(),
            voice_agent_version=VOICE_AGENT_VERSION,
            prompt_version=VOICE_PROMPT_VERSION,
            lifecycle_version=0,
        )
        self.session.add(call)
        try:
            self.session.flush()
            if source == "operator":
                self._event(call, "MANUAL_CALL_REQUESTED", "operator", {"reason": "operator_requested_call"})
            self._event(call, "CALL_QUEUED", "system", {"scenario": scenario.value}, input_hash=call.input_hash)
            started = self.provider.start_call(context, idempotency_key=key, scenario=scenario)
            call.provider_call_reference = started.provider_call_reference
            call.provider = started.provider
            call.started_at = self._now()
            self._transition(call, VoiceCallStatus.CALL_INITIATED)
            self._event(call, "CALL_INITIATED", "provider", {"provider": started.provider})
            self.session.commit()
        except VoiceProviderError as exc:
            call.failure_code = safe_failure_code(exc.code)
            call.completed_at = self._now()
            self._transition(call, VoiceCallStatus.FAILED)
            failure_payload = {"failure_code": call.failure_code}
            if exc.provider_code:
                failure_payload["failure_classification"] = exc.provider_code
            if exc.reason:
                failure_payload["failure_reason"] = exc.reason
            self._event(call, "CALL_FAILED", "provider", failure_payload)
            self.session.commit()
            raise VoiceProviderFailure(call.failure_code) from None
        except IntegrityError as exc:
            self.session.rollback()
            existing = self.session.scalar(select(VoiceCall).where(VoiceCall.idempotency_key == key))
            if existing is not None:
                return self.get_call(existing.id), False
            raise VoiceDuplicateError("voice call could not be created") from exc
        return self.get_call(call.id), True

    def start_manual_for_case(self, recovery_case_id: str) -> VoiceCall:
        """Place one operator-requested call without changing the stored decision."""
        case = self.session.get(RecoveryCase, recovery_case_id)
        if case is None:
            raise VoiceNotFoundError("recovery case not found")
        if case.status in {"RECOVERED", "CLOSED"}:
            raise VoiceActionNotAllowedError("cannot call a completed recovery case")
        if not case.customer_phone:
            raise VoiceActionNotAllowedError("manual call requires a customer phone number")
        intervention = self.session.scalar(
            select(Intervention)
            .where(Intervention.recovery_case_id == recovery_case_id)
            .order_by(Intervention.created_at.desc(), Intervention.id.desc())
        )
        if intervention is None:
            raise VoiceActionNotAllowedError("manual call requires a stored intervention")
        call, _ = self.start(
            intervention.id,
            VoiceScenario.CUSTOMER_AGREES_TO_PAY,
            allow_secondary=True,
            source="operator",
        )
        return call

    def run_demo(self, intervention_id: str, scenario: VoiceScenario) -> VoiceCall:
        if self.provider.name != "local":
            raise VoiceProviderFailure("demo_requires_local_provider")
        try:
            call, _ = self.start(intervention_id, scenario)
        except VoiceProviderFailure:
            if scenario == VoiceScenario.PROVIDER_FAILURE:
                return self.get_call_for_intervention(intervention_id)
            raise
        if call.status in TERMINAL_VOICE_STATUSES:
            return call
        self._advance(call, VoiceCallStatus.RINGING, "CALL_RINGING", "local")
        if scenario == VoiceScenario.NO_ANSWER:
            self._complete(call, VoiceCallStatus.NO_ANSWER, "NO_ANSWER", {"reason": "no_answer"})
            self.session.commit()
            return self.get_call(call.id)
        self._advance(call, VoiceCallStatus.CONNECTED, "CALL_CONNECTED", "local")
        self._advance(call, VoiceCallStatus.CONVERSATION, "CONVERSATION_STARTED", "local")
        context = build_voice_context(call.intervention, allow_secondary=True)
        agent = VoiceAgent(context)
        now = self._demo_timestamp(call, 0)
        self._record_turn(call, agent.opening_turn(now), context)
        customer_text = {
            VoiceScenario.CUSTOMER_AGREES_TO_PAY: "Yes, I can pay now.",
            VoiceScenario.CUSTOMER_REQUESTS_PAYMENT_LINK: "Please send me a payment link.",
            VoiceScenario.CUSTOMER_REQUESTS_RETRY_LATER: "Please retry later.",
            VoiceScenario.CUSTOMER_ALREADY_PAID: "I already paid.",
            VoiceScenario.CUSTOMER_DECLINES: "I do not want to continue.",
        }[scenario]
        customer_turn = agent.customer_turn(customer_text, self._demo_timestamp(call, 1))
        self._record_turn(call, customer_turn, context)
        self._advance(call, VoiceCallStatus.AWAITING_RESOLUTION, "AWAITING_RESOLUTION", "local")
        intent = customer_turn.intent
        call.outcome_intent = intent.value if intent else VoiceIntent.UNKNOWN.value
        payment_link = None
        if intent == VoiceIntent.SEND_PAYMENT_LINK:
            if self.payment_service is None:
                raise VoiceProviderFailure("payment_service_unavailable")
            payment = self.payment_service.create_for_voice_intent(call.intervention_id, intent.value)
            payment_link = payment.short_url
            call.payment_link = payment_link
            self._event(call, "PAYMENT_LINK_ATTACHED", "payment_service", {"payment_id": payment.id, "provider": payment.provider})
            if self.messaging_service is not None:
                try:
                    message = self.messaging_service.send_for_voice_link(call.intervention_id, payment_link)
                    self._event(call, "PAYMENT_LINK_NOTIFIED", "messaging_service", {"message_id": message.id, "provider": message.provider, "provider_message_id": message.provider_message_id})
                except Exception as exc:
                    self._event(call, "PAYMENT_LINK_NOTIFICATION_FAILED", "messaging_service", {"provider": getattr(self.messaging_service.provider, "name", "unknown"), "error": str(exc)[:128]})
        response = agent.response_turn(intent or VoiceIntent.UNKNOWN, self._demo_timestamp(call, 2), payment_link=payment_link)
        self._record_turn(call, response, context)
        if intent in {VoiceIntent.DECLINE, VoiceIntent.WRONG_PERSON}:
            self.interventions.record_outcome(
                call.intervention_id,
                InterventionOutcomeCreate(
                    status="NOT_RECOVERED",
                    recovered_amount_paise=0,
                    currency=call.intervention.recovery_case.currency,
                    occurred_at=self._demo_timestamp(call, 2),
                    source="voice_agent",
                ),
            )
            self._complete(call, VoiceCallStatus.DECLINED, "CALL_DECLINED", {"intent": intent.value})
        else:
            self._complete(call, VoiceCallStatus.COMPLETED, "CALL_COMPLETED", {"intent": (intent.value if intent else VoiceIntent.UNKNOWN.value), "payment_link_attached": payment_link is not None})
        self.session.commit()
        return self.get_call(call.id)

    def twilio_twiml(self, intervention_id: str) -> str:
        """Return the first TwiML turn for a real trial call."""
        call = self.get_call_for_intervention(intervention_id)
        if call.status in TERMINAL_VOICE_STATUSES:
            return self._twiml_say("This recovery call is already complete. Thank you. Goodbye.")
        context = build_voice_context(call.intervention, allow_secondary=True)
        if not call.turns:
            self._record_turn(call, VoiceAgent(context).opening_turn(self._now()), context)
            self.session.commit()
        self._bring_to_conversation(call, source="twilio")
        self.session.commit()
        prompt = "नमस्ते। आपके recent payment में problem आई थी। क्या आप अभी payment link लेना चाहेंगे, या बाद में try करेंगे?"
        return self._twiml_record(prompt, intervention_id)

    def exotel_opening(self, intervention_id: str) -> str:
        """Prepare the first live Exotel turn and return the Hinglish prompt."""
        call = self.get_call_for_intervention(intervention_id)
        if call.status in TERMINAL_VOICE_STATUSES:
            return "यह recovery call पहले ही complete हो चुकी है। धन्यवाद।"
        context = build_voice_context(call.intervention, allow_secondary=True)
        if not call.turns:
            self._record_turn(call, VoiceAgent(context).opening_turn(self._now()), context)
        self._bring_to_conversation(call, source="exotel")
        self.session.commit()
        return call.turns[0].text

    def exotel_stream_opened(self, intervention_id: str, stream_sid: str | None = None) -> VoiceCall:
        """Persist the point at which Exotel hands the call to the bot."""
        call = self.get_call_for_intervention(intervention_id)
        if call.status in TERMINAL_VOICE_STATUSES:
            return call
        self._bring_to_conversation(call, source="exotel")
        payload = {"stream_connected": True}
        if stream_sid:
            payload["stream_sid"] = stream_sid[:128]
        self._event(call, "STREAM_CONNECTED", "exotel", payload)
        self.session.commit()
        return self.get_call(call.id)

    def exotel_stream_failed(self, intervention_id: str | None, *, stage: str, code: str, message: str | None = None) -> None:
        """Persist a visible bridge/provider failure instead of silently dropping the call."""
        if not intervention_id:
            return
        try:
            call = self.get_call_for_intervention(intervention_id)
        except VoiceNotFoundError:
            return
        safe_code = safe_failure_code(code, default="voice_stream_failure")
        payload = {"stage": stage, "failure_code": safe_code}
        if message:
            payload["failure_reason"] = message[:255]
        if getattr(self.speech_provider, "name", None):
            payload["provider"] = self.speech_provider.name
        if call.status not in TERMINAL_VOICE_STATUSES:
            call.failure_code = safe_code
            call.completed_at = self._now()
            self._transition(call, VoiceCallStatus.FAILED)
        self._event(call, "VOICE_STREAM_FAILED", "sarvam" if stage == "sarvam" else "exotel", payload)
        self.session.commit()

    def handle_exotel_transcript(self, intervention_id: str, transcript: str) -> tuple[str, bool]:
        """Apply one Sarvam transcript to the controlled recovery conversation."""
        return self._handle_customer_text(intervention_id, transcript, source="exotel", complete=False)

    def _handle_customer_text(self, intervention_id: str, text: str, *, source: str, complete: bool) -> tuple[str, bool]:
        call = self.get_call_for_intervention(intervention_id)
        if call.status in TERMINAL_VOICE_STATUSES:
            return "यह recovery call पहले ही complete हो चुकी है। धन्यवाद।", True
        text = text.strip()
        if not text:
            return "कृपया payment link, बाद में, already paid, या no thanks बोलिए।", False
        self._bring_to_conversation(call, source=source)
        context = build_voice_context(call.intervention, allow_secondary=True)
        agent = VoiceAgent(context)
        turn = agent.customer_turn(text, self._now())
        self._record_turn(call, turn, context)
        if source == "exotel":
            self._event(call, "SPEECH_TRANSCRIBED", "sarvam", {"transcript_length": len(text), "language_code": getattr(self.speech_provider, "language_code", "hi-IN"), "model": getattr(self.speech_provider, "stt_model", "saaras:v3")})
        if call.status != VoiceCallStatus.AWAITING_RESOLUTION.value:
            self._advance(call, VoiceCallStatus.AWAITING_RESOLUTION, "AWAITING_RESOLUTION", source)
        intent = turn.intent or VoiceIntent.UNKNOWN
        call.outcome_intent = intent.value
        payment_link = None
        if intent in {VoiceIntent.PAY_NOW, VoiceIntent.SEND_PAYMENT_LINK}:
            if self.payment_service is None:
                raise VoiceProviderFailure("payment_service_unavailable")
            payment = self.payment_service.create_for_voice_intent(call.intervention_id, "SEND_PAYMENT_LINK")
            payment_link = payment.short_url
            call.payment_link = payment_link
            self._event(call, "PAYMENT_LINK_ATTACHED", "payment_service", {"payment_id": payment.id, "provider": payment.provider})
            if self.messaging_service is not None:
                try:
                    message = self.messaging_service.send_for_voice_link(call.intervention_id, payment_link)
                    self._event(call, "PAYMENT_LINK_NOTIFIED", "messaging_service", {"message_id": message.id, "provider": message.provider, "provider_message_id": message.provider_message_id})
                except Exception as exc:
                    self._event(call, "PAYMENT_LINK_NOTIFICATION_FAILED", "messaging_service", {"provider": getattr(self.messaging_service.provider, "name", "unknown"), "error": str(exc)[:128]})
        response_text = {
            VoiceIntent.PAY_NOW: "Payment link ready है। कृपया अभी complete कीजिए। Razorpay success confirm करेगा, तभी recovery mark होगी।",
            VoiceIntent.SEND_PAYMENT_LINK: "Payment link ready है और approved message channel के लिए request record हो गई है। Payment confirm होने के बाद ही recovery mark होगी।",
            VoiceIntent.RETRY_LATER: "बाद में try करने की request record हो गई है। अभी payment recovered mark नहीं हुआ है।",
            VoiceIntent.ALREADY_PAID: "आपकी payment claim record हो गई है। Recovery से पहले payment team verify करेगी।",
            VoiceIntent.DECLINE: "समझ गया। आप continue नहीं करना चाहते, यह record कर लिया है।",
            VoiceIntent.WRONG_PERSON: "समझ गया। यह गलत number है, मैं call end कर रहा हूँ।",
        }.get(intent, "मैं incorrect information नहीं देना चाहता। आपका response record कर लिया है और team follow up करेगी।")
        response = agent.response_turn(intent, self._now(), payment_link=None)
        response = response.model_copy(update={"text": response_text})
        self._record_turn(call, response, context)
        if intent in {VoiceIntent.DECLINE, VoiceIntent.WRONG_PERSON}:
            if complete:
                self._complete(call, VoiceCallStatus.DECLINED, "CALL_DECLINED", {"intent": intent.value})
                self.interventions.record_outcome(call.intervention_id, InterventionOutcomeCreate(status="NOT_RECOVERED", recovered_amount_paise=0, currency=call.intervention.recovery_case.currency, occurred_at=self._now(), source="voice_agent"))
        elif complete:
            self._complete(call, VoiceCallStatus.COMPLETED, "CALL_COMPLETED", {"intent": intent.value, "payment_link_attached": payment_link is not None})
        self.session.commit()
        should_end = complete or intent in {VoiceIntent.DECLINE, VoiceIntent.WRONG_PERSON}
        return response_text, should_end

    def handle_twilio_gather(self, intervention_id: str, speech: str | None, digits: str | None) -> str:
        """Persist one spoken/DTMF turn and return the next TwiML response."""
        text = speech or ("yes" if digits == "1" else "later" if digits == "2" else "")
        if not text.strip():
            return self._twiml_record("कृपया payment link, बाद में, already paid, या no thanks बोलिए।", intervention_id)
        response_text, _ = self._handle_customer_text(intervention_id, text, source="twilio", complete=True)
        return self._twiml_say(response_text)

    def handle_twilio_record(self, intervention_id: str, recording_url: str | None, fields: dict[str, str], signature: str, callback_url: str) -> str:
        """Transcribe a caller recording with Sarvam, then run the normal intent loop."""
        if not isinstance(self.provider, TwilioVoiceProvider) or not self.provider.verify_twilio_request(callback_url, fields, signature):
            raise InvalidVoiceWebhookError("invalid webhook signature")
        if self.speech_provider is None:
            raise VoiceProviderFailure("sarvam_unavailable")
        if not recording_url:
            return self._twiml_record("मुझे आपकी आवाज़ clear नहीं सुनाई दी। कृपया फिर से बोलिए।", intervention_id)
        try:
            audio = self.provider.fetch_recording(recording_url)
            transcript = self.speech_provider.transcribe(audio, content_type="audio/wav")
        except (VoiceProviderError, SarvamSpeechError) as exc:
            call = self.get_call_for_intervention(intervention_id)
            self._event(call, "SPEECH_TRANSCRIPTION_FAILED", "sarvam", {"failure_code": getattr(exc, "code", "provider_request_failed")})
            self.session.commit()
            return self._twiml_record("मुझे आपकी आवाज़ clear नहीं सुनाई दी। कृपया payment link, बाद में, या already paid बोलिए।", intervention_id)
        call = self.get_call_for_intervention(intervention_id)
        self._event(call, "SPEECH_TRANSCRIBED", "sarvam", {"transcript_length": len(transcript), "language_code": self.speech_provider.language_code, "model": self.speech_provider.stt_model})
        self.session.commit()
        return self.handle_twilio_gather(intervention_id, transcript, None)

    def handle_twilio_status(self, intervention_id: str, provider_call_reference: str | None, status: str, fields: dict[str, str], signature: str, callback_url: str) -> VoiceCall:
        if not isinstance(self.provider, TwilioVoiceProvider) or not self.provider.verify_twilio_request(callback_url, fields, signature):
            raise InvalidVoiceWebhookError("invalid webhook signature")
        call = self.get_call_for_intervention(intervention_id)
        reference = provider_call_reference or call.provider_call_reference
        if reference and call.provider_call_reference and reference != call.provider_call_reference:
            raise VoiceNotFoundError("voice call not found for provider reference")
        mapping = {"initiated": VoiceCallStatus.CALL_INITIATED, "ringing": VoiceCallStatus.RINGING, "in-progress": VoiceCallStatus.CONNECTED, "answered": VoiceCallStatus.CONNECTED, "completed": VoiceCallStatus.COMPLETED, "busy": VoiceCallStatus.FAILED, "failed": VoiceCallStatus.FAILED, "no-answer": VoiceCallStatus.NO_ANSWER, "canceled": VoiceCallStatus.CANCELLED}
        target = mapping.get(status.casefold())
        if target and call.status != target.value:
            try:
                if target == VoiceCallStatus.COMPLETED and call.status == VoiceCallStatus.CONNECTED:
                    self._advance(call, VoiceCallStatus.CONVERSATION, "CONVERSATION_STARTED", "twilio")
                    self._advance(call, VoiceCallStatus.AWAITING_RESOLUTION, "AWAITING_RESOLUTION", "twilio")
                self._transition(call, target)
                self._event(call, f"PROVIDER_{status.upper().replace('-', '_')}", "twilio", {"provider_call_reference": reference, "status": status})
                if target in TERMINAL_VOICE_STATUSES:
                    call.completed_at = self._now()
                self.session.commit()
            except VoiceDomainError:
                self.session.rollback()
        return self.get_call(call.id)

    def _bring_to_conversation(self, call: VoiceCall, *, source: str = "twilio") -> None:
        if call.status == VoiceCallStatus.CALL_INITIATED.value:
            self._advance(call, VoiceCallStatus.RINGING, "CALL_RINGING", source)
        if call.status == VoiceCallStatus.RINGING.value:
            self._advance(call, VoiceCallStatus.CONNECTED, "CALL_CONNECTED", source)
        if call.status == VoiceCallStatus.CONNECTED.value:
            self._advance(call, VoiceCallStatus.CONVERSATION, "CONVERSATION_STARTED", source)

    def _twiml_say(self, text: str) -> str:
        language = html.escape(str(getattr(self.provider, "language", "hi-IN")), quote=True)
        audio_url = self._speech_audio_url(text)
        if audio_url:
            return f'<?xml version="1.0" encoding="UTF-8"?><Response><Play>{html.escape(audio_url)}</Play><Hangup/></Response>'
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Say language="{language}">{html.escape(text)}</Say><Hangup/></Response>'

    def _twiml_gather(self, prompt: str, intervention_id: str) -> str:
        language = html.escape(str(getattr(self.provider, "language", "hi-IN")), quote=True)
        action = html.escape(f"/api/v1/voice/twilio/gather?intervention_id={intervention_id}", quote=True)
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Gather input="speech dtmf" language="{language}" action="{action}" method="POST" timeout="5" numDigits="1"><Say language="{language}">{html.escape(prompt)}</Say></Gather><Say language="{language}">I did not hear a response. Goodbye.</Say><Hangup/></Response>'

    def _twiml_record(self, prompt: str, intervention_id: str) -> str:
        """Speak with Sarvam and capture caller audio for Saaras transcription."""
        if not isinstance(self.provider, TwilioVoiceProvider) or not self._speech_is_configured():
            return self._twiml_gather(prompt, intervention_id)
        audio_url = self._speech_audio_url(prompt)
        if not audio_url:
            return self._twiml_gather(prompt, intervention_id)
        action = html.escape(f"{self.provider.public_base_url}/api/v1/voice/twilio/record?intervention_id={intervention_id}", quote=True)
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Play>{html.escape(audio_url)}</Play><Record action="{action}" method="POST" maxLength="12" timeout="5" playBeep="false" trim="trim-silence"/></Response>'

    def _speech_is_configured(self) -> bool:
        return bool(self.speech_provider and self.speech_provider.enabled and self.speech_provider.api_key)

    def _speech_audio_url(self, text: str) -> str | None:
        if not self._speech_is_configured() or not isinstance(self.provider, TwilioVoiceProvider) or not self.provider.public_base_url:
            return None
        try:
            token = self.speech_provider.audio_token(text)
        except SarvamSpeechError:
            return None
        return f"{self.provider.public_base_url}/api/v1/voice/sarvam/audio/{token}"

    def handle_webhook(self, provider_name: str, event: VoiceWebhookEvent) -> VoiceCall:
        if self.provider.name != provider_name:
            raise InvalidVoiceWebhookError("provider is not configured for this webhook boundary")
        if not self.provider.verify_webhook(event):
            raise InvalidVoiceWebhookError("invalid webhook signature")
        existing_event = self.session.scalar(select(VoiceEvent).where(VoiceEvent.event_id == event.event_id))
        if existing_event is not None:
            return self.get_call(existing_event.call_id)
        call = self.session.scalar(select(VoiceCall).where(VoiceCall.provider_call_reference == event.provider_call_reference))
        if call is None:
            raise VoiceNotFoundError("voice call not found for provider reference")
        target = self._webhook_target(event.event_type)
        if target is not None:
            self._transition(call, target)
            if target in TERMINAL_VOICE_STATUSES:
                call.completed_at = event.event_timestamp
        self._event(call, f"PROVIDER_{event.event_type.upper()}", "provider", {"provider_event_id": event.event_id, "provider_event_type": event.event_type, "processing_result": "applied"}, event_id=event.event_id, provider_event_hash=self._webhook_hash(event))
        self.session.commit()
        return self.get_call(call.id)

    def _assert_voice_intervention(self, intervention: Intervention, *, allow_secondary: bool = False) -> None:
        if not allow_secondary and (intervention.action != "VOICE_RECOVERY" or intervention.decision.selected_action != "VOICE_RECOVERY"):
            raise VoiceActionNotAllowedError("voice execution is only allowed for VOICE_RECOVERY")

    def _advance(self, call: VoiceCall, target: VoiceCallStatus, event_type: str, source: str) -> None:
        self._transition(call, target)
        self._event(call, event_type, source, {})

    def _complete(self, call: VoiceCall, target: VoiceCallStatus, event_type: str, payload: dict) -> None:
        call.completed_at = self._now()
        self._transition(call, target)
        self._event(call, event_type, "system", payload)

    def _transition(self, call: VoiceCall, target: VoiceCallStatus) -> None:
        validate_voice_transition(call.status, target)
        call.status = target.value
        call.lifecycle_version += 1
        call.updated_at = self._now()

    def _record_turn(self, call: VoiceCall, turn: ConversationTurn, context: VoiceContext) -> VoiceTurn:
        sequence = self._next_turn_sequence(call.id)
        row = VoiceTurn(
            call_id=call.id,
            sequence_number=sequence,
            speaker=turn.speaker,
            text=turn.text,
            intent=turn.intent.value if turn.intent else None,
            confidence=turn.confidence,
            requested_action=turn.requested_action,
            requires_confirmation=turn.requires_confirmation,
            timestamp=turn.timestamp,
            validated=turn.validated,
        )
        call.turns.append(row)
        self.session.flush()
        call.transcript_hash = transcript_hash(call.turns)
        self._event(call, "CONVERSATION_TURN", "agent" if turn.speaker == "agent" else "customer", {"turn_id": row.id, "speaker": turn.speaker, "intent": row.intent}, input_hash=context_hash(context), transcript_hash=call.transcript_hash)
        return row

    def _event(self, call: VoiceCall, event_type: str, source: str, payload: dict, *, input_hash: str | None = None, transcript_hash: str | None = None, event_id: str | None = None, provider_event_hash: str | None = None) -> VoiceEvent:
        persisted = int(self.session.scalar(select(func.max(VoiceEvent.sequence_number)).where(VoiceEvent.call_id == call.id)) or 0)
        pending = max((event.sequence_number for event in self.session.new if isinstance(event, VoiceEvent) and event.call_id == call.id), default=0)
        event = VoiceEvent(
            call_id=call.id,
            event_id=event_id or f"voice-event-{uuid4().hex}",
            event_type=event_type,
            source=source,
            provider_mode=self.provider.mode,
            payload_json=payload,
            provider_event_hash=provider_event_hash,
            input_hash=input_hash,
            transcript_hash=transcript_hash,
            voice_agent_version=VOICE_AGENT_VERSION,
            prompt_version=VOICE_PROMPT_VERSION,
            sequence_number=max(persisted, pending) + 1,
        )
        call.events.append(event)
        return event

    @staticmethod
    def _webhook_hash(event: VoiceWebhookEvent) -> str:
        canonical = json.dumps({
            "event_id": event.event_id,
            "provider_call_reference": event.provider_call_reference,
            "event_type": event.event_type,
            "event_timestamp": event.event_timestamp.isoformat(),
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _next_turn_sequence(self, call_id: str) -> int:
        persisted = int(self.session.scalar(select(func.max(VoiceTurn.sequence_number)).where(VoiceTurn.call_id == call_id)) or 0)
        pending = max((turn.sequence_number for turn in self.session.new if isinstance(turn, VoiceTurn) and turn.call_id == call_id), default=0)
        return max(persisted, pending) + 1

    @staticmethod
    def _idempotency_key(intervention_id: str, scenario: VoiceScenario, provider: str) -> str:
        return hashlib.sha256(f"chimera-voice-v1|{intervention_id}|{scenario.value}|{provider}".encode("utf-8")).hexdigest()

    @staticmethod
    def _empty_transcript_hash() -> str:
        return hashlib.sha256(b"[]").hexdigest()

    @staticmethod
    def _demo_timestamp(call: VoiceCall, offset_seconds: int) -> datetime:
        seed = int(hashlib.sha256(call.idempotency_key.encode("utf-8")).hexdigest()[:8], 16) % 86400
        return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seed + offset_seconds)

    @staticmethod
    def _webhook_target(event_type: str) -> VoiceCallStatus | None:
        return {
            "call_initiated": VoiceCallStatus.CALL_INITIATED,
            "ringing": VoiceCallStatus.RINGING,
            "connected": VoiceCallStatus.CONNECTED,
            "conversation": VoiceCallStatus.CONVERSATION,
            "awaiting_resolution": VoiceCallStatus.AWAITING_RESOLUTION,
            "completed": VoiceCallStatus.COMPLETED,
            "declined": VoiceCallStatus.DECLINED,
            "no_answer": VoiceCallStatus.NO_ANSWER,
            "failed": VoiceCallStatus.FAILED,
            "cancelled": VoiceCallStatus.CANCELLED,
        }.get(event_type)
