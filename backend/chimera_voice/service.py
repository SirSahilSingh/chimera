from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.db.models import Intervention, VoiceCall, VoiceEvent, VoiceTurn
from backend.app.interventions.service import InterventionService
from backend.app.interventions.state_machine import InterventionStatus
from backend.app.schemas import InterventionOutcomeCreate

from .agent import VoiceAgent
from .context import build_voice_context, context_hash
from .errors import InvalidVoiceWebhookError, VoiceActionNotAllowedError, VoiceDuplicateError, VoiceNotFoundError, VoiceProviderFailure
from .provider import VoiceProvider, VoiceProviderError
from .schemas import ConversationTurn, VoiceContext, VoiceIntent, VoiceScenario, VoiceWebhookEvent
from .state_machine import TERMINAL_VOICE_STATUSES, VoiceCallStatus, validate_voice_transition
from .transcript import payload_hash, transcript_hash
from .versions import VOICE_AGENT_VERSION, VOICE_PROMPT_VERSION


class VoiceService:
    """Coordinates a voice call without decision or policy authority."""

    def __init__(self, session: Session, provider: VoiceProvider, intervention_service: InterventionService | None = None, payment_service=None) -> None:
        self.session = session
        self.provider = provider
        self.interventions = intervention_service or InterventionService(session)
        self.payment_service = payment_service

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

    def start(self, intervention_id: str, scenario: VoiceScenario) -> tuple[VoiceCall, bool]:
        intervention = self.interventions.get_intervention(intervention_id)
        self._assert_voice_intervention(intervention)
        existing = self.session.scalar(select(VoiceCall).where(VoiceCall.intervention_id == intervention_id))
        if existing is not None:
            if existing.scenario != scenario.value:
                raise VoiceDuplicateError("intervention already has a voice call with a different scenario")
            return self.get_call(existing.id), False

        if intervention.status == InterventionStatus.READY.value:
            self.interventions.execute(intervention.id)
            intervention = self.interventions.get_intervention(intervention.id)
        if intervention.status != InterventionStatus.AWAITING_OUTCOME.value:
            raise VoiceActionNotAllowedError(f"voice call requires an executable intervention, got {intervention.status}")

        context = build_voice_context(intervention)
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
            self._event(call, "CALL_QUEUED", "system", {"scenario": scenario.value}, input_hash=call.input_hash)
            started = self.provider.start_call(context, idempotency_key=key, scenario=scenario)
            call.provider_call_reference = started.provider_call_reference
            call.provider = started.provider
            call.started_at = self._now()
            self._transition(call, VoiceCallStatus.CALL_INITIATED)
            self._event(call, "CALL_INITIATED", "provider", {"provider": started.provider})
            self.session.commit()
        except VoiceProviderError as exc:
            call.failure_code = exc.code
            call.completed_at = self._now()
            self._transition(call, VoiceCallStatus.FAILED)
            self._event(call, "CALL_FAILED", "provider", {"failure_code": exc.code})
            self.session.commit()
            raise VoiceProviderFailure(exc.code) from None
        except IntegrityError as exc:
            self.session.rollback()
            existing = self.session.scalar(select(VoiceCall).where(VoiceCall.idempotency_key == key))
            if existing is not None:
                return self.get_call(existing.id), False
            raise VoiceDuplicateError("voice call could not be created") from exc
        return self.get_call(call.id), True

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
        context = build_voice_context(call.intervention)
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
        self._event(call, f"PROVIDER_{event.event_type.upper()}", "provider", {"provider_event_id": event.event_id, "provider_event_type": event.event_type}, event_id=event.event_id)
        self.session.commit()
        return self.get_call(call.id)

    def _assert_voice_intervention(self, intervention: Intervention) -> None:
        if intervention.action != "VOICE_RECOVERY" or intervention.decision.selected_action != "VOICE_RECOVERY":
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

    def _event(self, call: VoiceCall, event_type: str, source: str, payload: dict, *, input_hash: str | None = None, transcript_hash: str | None = None, event_id: str | None = None) -> VoiceEvent:
        persisted = int(self.session.scalar(select(func.max(VoiceEvent.sequence_number)).where(VoiceEvent.call_id == call.id)) or 0)
        pending = max((event.sequence_number for event in self.session.new if isinstance(event, VoiceEvent) and event.call_id == call.id), default=0)
        event = VoiceEvent(
            call_id=call.id,
            event_id=event_id or f"voice-event-{uuid4().hex}",
            event_type=event_type,
            source=source,
            provider_mode=self.provider.mode,
            payload_json=payload,
            input_hash=input_hash,
            transcript_hash=transcript_hash,
            voice_agent_version=VOICE_AGENT_VERSION,
            prompt_version=VOICE_PROMPT_VERSION,
            sequence_number=max(persisted, pending) + 1,
        )
        call.events.append(event)
        return event

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
