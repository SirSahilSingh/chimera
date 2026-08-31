from __future__ import annotations

import hashlib
import json

from backend.app.interventions.errors import ActionMismatchError, InvalidExecutionContextError

from .schemas import VoiceContext


def build_voice_context(intervention, *, payment_link: str | None = None) -> VoiceContext:
    decision = intervention.decision
    case = intervention.recovery_case
    if decision is None or case is None:
        raise InvalidExecutionContextError("voice intervention context is unavailable")
    if intervention.action != "VOICE_RECOVERY" or decision.selected_action != "VOICE_RECOVERY":
        raise ActionMismatchError("voice execution requires the stored VOICE_RECOVERY action")
    return VoiceContext(
        intervention_id=intervention.id,
        recovery_case_id=case.id,
        decision_id=decision.id,
        customer_phone=case.customer_phone,
        selected_action="VOICE_RECOVERY",
        payment_amount_paise=case.amount_paise,
        currency=case.currency,
        failure_reason=case.failure_reason,
        payment_method=case.payment_method,
        incident_flag=case.incident_flag,
        allowed_recovery_options=("PAY_NOW", "SEND_PAYMENT_LINK", "RETRY_LATER", "CALLBACK_REQUEST"),
        payment_link=payment_link,
    )


def context_hash(context: VoiceContext) -> str:
    encoded = json.dumps(context.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
