from __future__ import annotations

from .schemas import VoiceContext, VoiceIntent


SYSTEM_PROMPT = """You are CHIMERA's controlled recovery voice assistant.
You may explain the stored payment issue and record a customer intent. You may
not choose or change a recovery action, promise a discount, invent a payment
amount, claim a payment succeeded, or expose hidden decision/model data.
"""


def opening_message(context: VoiceContext) -> str:
    amount = f"INR {context.payment_amount_paise / 100:.2f}"
    return f"Hello. I am calling about a recent payment of {amount} that could not be completed. Would you like to resolve it now, receive a payment link, or try again later?"


def response_for_intent(intent: VoiceIntent, *, payment_link: str | None = None) -> str:
    if intent == VoiceIntent.PAY_NOW:
        return "Thank you. I recorded that you are ready to resolve it now. The payment is not marked recovered until the payment system confirms success."
    if intent == VoiceIntent.SEND_PAYMENT_LINK:
        return f"I recorded your request for a payment link. Here is the demo link: {payment_link}" if payment_link else "I recorded your request for a payment link. The appropriate team can provide it through the approved channel."
    if intent == VoiceIntent.RETRY_LATER:
        return "I recorded that you would prefer to try again later. No payment has been marked recovered."
    if intent == VoiceIntent.ALREADY_PAID:
        return "Thank you. I recorded that you already paid. The payment team will verify it; I will not mark recovery from this conversation alone."
    if intent == VoiceIntent.CALLBACK_REQUEST:
        return "I recorded your callback request for the appropriate team."
    if intent == VoiceIntent.DECLINE:
        return "Understood. I will record that you do not want to continue."
    if intent == VoiceIntent.WRONG_PERSON:
        return "Understood. I will record that this is the wrong number and end the call."
    return "I do not want to give you incorrect information. I can record your response and have the appropriate team follow up."
