from __future__ import annotations

from .context import MessagingContext


def validate_messaging_context(context: MessagingContext) -> MessagingContext:
    if context.selected_action not in {"SEND_MESSAGE", "PAYMENT_LINK"}:
        raise ValueError("messaging context requires SEND_MESSAGE or PAYMENT_LINK")
    if context.currency != "INR" or type(context.amount_paise) is not int:
        raise ValueError("message context must use integer INR paise")
    return context
