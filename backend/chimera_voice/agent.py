from __future__ import annotations

from .prompts import opening_message, response_for_intent
from .schemas import ConversationTurn, VoiceContext, VoiceIntent
from .validation import validate_turn


class VoiceAgent:
    """Controlled local conversation policy; it has no decision authority."""

    def __init__(self, context: VoiceContext) -> None:
        self.context = context

    def opening_turn(self, timestamp) -> ConversationTurn:
        return validate_turn(
            ConversationTurn(
                speaker="agent",
                text=opening_message(self.context),
                intent=None,
                confidence=1.0,
                requested_action=None,
                requires_confirmation=True,
                timestamp=timestamp,
                validated=True,
            ),
            self.context,
        )

    def classify_customer_text(self, text: str) -> VoiceIntent:
        normalized = text.casefold()
        if "wrong number" in normalized or "wrong person" in normalized or "not me" in normalized:
            return VoiceIntent.WRONG_PERSON
        if "already paid" in normalized or "paid already" in normalized:
            return VoiceIntent.ALREADY_PAID
        if "payment link" in normalized or "send the link" in normalized or "link" in normalized:
            return VoiceIntent.SEND_PAYMENT_LINK
        if "later" in normalized or "tomorrow" in normalized or "retry" in normalized:
            return VoiceIntent.RETRY_LATER
        if "call back" in normalized or "callback" in normalized:
            return VoiceIntent.CALLBACK_REQUEST
        if "not interested" in normalized or "do not want" in normalized or normalized.strip() in {"no", "no thanks"}:
            return VoiceIntent.DECLINE
        if "yes" in normalized or "pay now" in normalized or "i can pay" in normalized:
            return VoiceIntent.PAY_NOW
        if "?" in text or normalized.startswith(("why", "how", "what")):
            return VoiceIntent.QUESTION
        return VoiceIntent.UNKNOWN

    def customer_turn(self, text: str, timestamp) -> ConversationTurn:
        intent = self.classify_customer_text(text)
        requested_action = "PAYMENT_LINK" if intent == VoiceIntent.SEND_PAYMENT_LINK else "RETRY_LATER" if intent == VoiceIntent.RETRY_LATER else None
        return validate_turn(
            ConversationTurn(
                speaker="customer",
                text=text,
                intent=intent,
                confidence=1.0,
                requested_action=requested_action,
                requires_confirmation=intent in {VoiceIntent.PAY_NOW, VoiceIntent.SEND_PAYMENT_LINK, VoiceIntent.RETRY_LATER, VoiceIntent.CALLBACK_REQUEST},
                timestamp=timestamp,
                validated=True,
            ),
            self.context,
        )

    def response_turn(self, intent: VoiceIntent, timestamp, *, payment_link: str | None = None) -> ConversationTurn:
        return validate_turn(
            ConversationTurn(
                speaker="agent",
                text=response_for_intent(intent, payment_link=payment_link),
                intent=None,
                confidence=1.0,
                requested_action=None,
                requires_confirmation=False,
                timestamp=timestamp,
                validated=True,
            ),
            self.context.model_copy(update={"payment_link": payment_link}) if payment_link else self.context,
        )
