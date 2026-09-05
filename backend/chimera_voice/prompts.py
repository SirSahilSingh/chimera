from __future__ import annotations

from .schemas import VoiceContext, VoiceIntent


SYSTEM_PROMPT = """You are CHIMERA's controlled recovery voice assistant.
You may explain the stored payment issue and record a customer intent. You may
not choose or change a recovery action, promise a discount, invent a payment
amount, claim a payment succeeded, or expose hidden decision/model data.
"""


def opening_message(context: VoiceContext) -> str:
    amount = f"INR {context.payment_amount_paise / 100:.2f}"
    return f"नमस्ते। आपके recent {amount} payment के बारे में call है, जो complete नहीं हो पाया। क्या आप अभी payment करना चाहेंगे, payment link लेना चाहेंगे, या बाद में try करेंगे?"


def response_for_intent(intent: VoiceIntent, *, payment_link: str | None = None) -> str:
    if intent == VoiceIntent.PAY_NOW:
        return "धन्यवाद। आप अभी payment करने के लिए ready हैं, यह record कर लिया है। Payment successful confirm होने के बाद ही recovery mark होगी।"
    if intent == VoiceIntent.SEND_PAYMENT_LINK:
        return f"Payment link के लिए आपकी request record कर ली है। यह link है: {payment_link}" if payment_link else "Payment link के लिए आपकी request record कर ली है। Approved channel से link share किया जाएगा।"
    if intent == VoiceIntent.RETRY_LATER:
        return "बाद में try करने की request record हो गई है। अभी payment recovered mark नहीं हुआ है। chimera se baat karne ke liye dhanyawad."
    if intent == VoiceIntent.ALREADY_PAID:
        return "धन्यवाद। आपने payment कर दिया है, यह record कर लिया है। Payment team verify करेगी; सिर्फ इस call से recovery mark नहीं होगी।"
    if intent == VoiceIntent.CALLBACK_REQUEST:
        return "आपकी callback request record कर ली है। Team आपसे approved channel पर contact करेगी।"
    if intent == VoiceIntent.DECLINE:
        return "समझ गया। आप continue नहीं करना चाहते, यह record कर लिया है।"
    if intent == VoiceIntent.WRONG_PERSON:
        return "समझ गया। यह गलत number है, मैं call end कर रहा हूँ।"
    return "Main incorrect information nahi dena chahta. Aapka response record kar liya hai aur team follow up karegi."
