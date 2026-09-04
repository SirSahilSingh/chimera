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
        normalized = " ".join(text.casefold().replace("।", ".").split())
        if any(phrase in normalized for phrase in ("wrong number", "wrong no", "wrong person", "not me", "galat number", "galat no", "yeh mera number nahi", "ye mera number nahi", "यह मेरा नंबर नहीं")):
            return VoiceIntent.WRONG_PERSON
        if any(phrase in normalized for phrase in ("already paid", "paid already", "maine pay kar diya", "maine payment kar diya", "payment kar diya", "paisa de diya", "paid kar diya", "pehle hi pay", "पहले ही भुगतान", "भुगतान कर दिया")):
            return VoiceIntent.ALREADY_PAID
        if any(phrase in normalized for phrase in ("payment link", "send the link", "send link", "link bhej", "link bhejo", "link bhej do", "link send", "whatsapp par", "व्हाट्सऐप पर", "लिंक भेज")):
            return VoiceIntent.SEND_PAYMENT_LINK
        if any(phrase in normalized for phrase in ("later", "tomorrow", "retry", "baad mein", "baad me", "kal", "thodi der", "phir try", "बाद में", "कल", "फिर कोशिश")):
            return VoiceIntent.RETRY_LATER
        if any(phrase in normalized for phrase in ("call back", "callback", "call karna", "wapas call", "वापस कॉल", "बाद में कॉल")):
            return VoiceIntent.CALLBACK_REQUEST
        if any(phrase in normalized for phrase in ("not interested", "do not want", "nahi chahiye", "nahin chahiye", "mat karo", "cancel", "नहीं चाहिए", "मत करो")) or normalized.strip() in {"no", "no thanks", "nahi", "nahin", "नहीं"}:
            return VoiceIntent.DECLINE
        if any(phrase in normalized for phrase in ("yes", "pay now", "i can pay", "haan", "han", "ji haan", "sahi hai", "theek hai", "accha", "hmm", "ok", "okay", "सही है", "ठीक है", "अच्छा", "हाँ", "abhi pay", "abhi payment", "pay kar", "payment karunga", "payment karungi", "kar deta", "kar dunga", "कर दूंगा", "अभी भुगतान")):
            return VoiceIntent.PAY_NOW
        if "?" in text or any(word in normalized for word in ("why", "how", "what", "kyun", "kyon", "kaise", "kya", "kiska", "kaunsa", "क्यों", "कैसे", "क्या", "किसका", "कौनसा")):
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
