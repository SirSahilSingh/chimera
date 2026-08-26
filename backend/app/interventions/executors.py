from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .context import ApprovedExecutionContext
from .errors import ExecutorUnavailableError


@dataclass(frozen=True)
class ExecutionResult:
    executor_type: str
    status: str
    provider_reference: str
    response: dict[str, str]
    error_code: str | None = None
    error_message_safe: str | None = None


class InterventionExecutor:
    action: str
    executor_type: str

    def execute(self, context: ApprovedExecutionContext) -> ExecutionResult:
        raise NotImplementedError


class DeterministicLocalExecutor(InterventionExecutor):
    def __init__(self, action: str, executor_type: str, acceptance_label: str) -> None:
        self.action = action
        self.executor_type = executor_type
        self.acceptance_label = acceptance_label

    def execute(self, context: ApprovedExecutionContext) -> ExecutionResult:
        if context.action != self.action:
            raise ExecutorUnavailableError("executor action does not match intervention action")
        request = json.dumps(context.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        reference = f"local:{hashlib.sha256(request.encode('utf-8')).hexdigest()[:24]}"
        return ExecutionResult(
            executor_type=self.executor_type,
            status="ACCEPTED",
            provider_reference=reference,
            response={"adapter": "deterministic_local", "action": self.action, "result": self.acceptance_label},
        )


class PaymentLinkExecutor(DeterministicLocalExecutor):
    def __init__(self) -> None:
        super().__init__("PAYMENT_LINK", "payment_link_local", "payment_link_creation_accepted")


class MessageExecutor(DeterministicLocalExecutor):
    def __init__(self) -> None:
        super().__init__("SEND_MESSAGE", "message_local", "message_dispatch_accepted")


class RetryExecutor(DeterministicLocalExecutor):
    def __init__(self, action: str) -> None:
        super().__init__(action, "retry_local", "retry_scheduled_accepted")


class VoiceRecoveryExecutor(DeterministicLocalExecutor):
    def __init__(self) -> None:
        super().__init__("VOICE_RECOVERY", "voice_local", "voice_intervention_accepted")


class EscalationExecutor(DeterministicLocalExecutor):
    def __init__(self) -> None:
        super().__init__("ESCALATE", "escalation_local", "escalation_created")


def default_executors() -> dict[str, InterventionExecutor]:
    return {
        "PAYMENT_LINK": PaymentLinkExecutor(),
        "SEND_MESSAGE": MessageExecutor(),
        "RETRY_NOW": RetryExecutor("RETRY_NOW"),
        "RETRY_LATER": RetryExecutor("RETRY_LATER"),
        "VOICE_RECOVERY": VoiceRecoveryExecutor(),
        "ESCALATE": EscalationExecutor(),
    }
