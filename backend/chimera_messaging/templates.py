from __future__ import annotations

import hashlib
import json

from .context import MessagingContext
from .versions import TEMPLATE_VERSION


TEMPLATES = {
    "expired_method": {
        "en": "Your payment method needs attention. Please use this secure link to complete your payment: {payment_link}",
        "hi": "Aapke payment method mein dikkat hai. Payment poora karne ke liye is secure link ka use karein: {payment_link}",
    },
    "insufficient_funds": {
        "en": "Your payment could not be completed. You can try another payment method here: {payment_link}",
        "hi": "Aapka payment poora nahi ho saka. Aap yahan doosra payment method try kar sakte hain: {payment_link}",
    },
    "technical_degradation": {
        "en": "We could not complete your payment because of a temporary issue. Please try again here: {payment_link}",
        "hi": "Temporary issue ki wajah se payment poora nahi ho saka. Kripya yahan dobara try karein: {payment_link}",
    },
    "issuer_decline": {
        "en": "Your bank declined the payment. Please try another payment method here: {payment_link}",
        "hi": "Aapke bank ne payment decline kiya. Kripya yahan doosra payment method try karein: {payment_link}",
    },
    "abandonment": {
        "en": "You can complete your pending payment securely here: {payment_link}",
        "hi": "Aap apna pending payment yahan securely poora kar sakte hain: {payment_link}",
    },
    "generic": {
        "en": "Please complete your payment securely here: {payment_link}",
        "hi": "Kripya apna payment yahan securely poora karein: {payment_link}",
    },
}


def template_key(failure_reason: str) -> str:
    return {"expired_method": "expired_method", "insufficient_funds": "insufficient_funds", "technical_degradation": "technical_degradation", "issuer_decline": "issuer_decline", "abandonment": "abandonment"}.get(failure_reason, "generic")


def render_message(context: MessagingContext) -> tuple[str, str, str, str]:
    key = template_key(context.failure_reason)
    language = context.language if context.language in TEMPLATES[key] else "en"
    link = context.payment_link or "the payment page"
    content = TEMPLATES[key][language].format(payment_link=link)
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    return key, TEMPLATE_VERSION, content, content_hash
