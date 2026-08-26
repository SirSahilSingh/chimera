from __future__ import annotations

import re

from .schemas import ConversationTurn, VoiceContext, VoiceIntent


class VoiceValidationError(ValueError):
    pass


INTENT_TO_REQUESTED_ACTION = {
    VoiceIntent.SEND_PAYMENT_LINK.value: "PAYMENT_LINK",
    VoiceIntent.RETRY_LATER.value: "RETRY_LATER",
}


def validate_turn(turn: ConversationTurn, context: VoiceContext) -> ConversationTurn:
    if not turn.validated:
        raise VoiceValidationError("conversation turn must be validated before persistence")
    if turn.speaker == "agent" and turn.intent is not None:
        raise VoiceValidationError("agent turns cannot claim a customer intent")
    if turn.speaker == "customer" and turn.intent is None:
        raise VoiceValidationError("customer turns require an extracted intent")
    if turn.intent is not None:
        expected_action = INTENT_TO_REQUESTED_ACTION.get(turn.intent.value)
        if turn.requested_action != expected_action:
            if expected_action is not None:
                raise VoiceValidationError("intent/action mapping is invalid")
            if turn.requested_action is not None:
                raise VoiceValidationError("this intent cannot request an action")
        if turn.requested_action is not None and turn.requested_action not in {"PAYMENT_LINK", "RETRY_LATER"}:
            raise VoiceValidationError("requested action is outside the voice allowlist")
    # Prevent agent text from inventing a monetary value. Displaying the
    # stored amount is allowed; no other numeric claim is allowed in a turn.
    numbers = re.findall(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?![A-Za-z0-9])", turn.text)
    if turn.speaker == "agent" and numbers:
        allowed = {
            str(context.payment_amount_paise),
            str(context.payment_amount_paise // 100),
            f"{context.payment_amount_paise // 100}.{context.payment_amount_paise % 100:02d}",
            "00",
        }
        if any(number not in allowed for number in numbers):
            raise VoiceValidationError("agent text contains an unapproved numeric value")
    return turn
