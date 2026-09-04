from __future__ import annotations

from enum import StrEnum

from backend.app.domain import DomainError


class VoiceCallStatus(StrEnum):
    CALL_QUEUED = "CALL_QUEUED"
    CALL_INITIATED = "CALL_INITIATED"
    RINGING = "RINGING"
    CONNECTED = "CONNECTED"
    CONVERSATION = "CONVERSATION"
    AWAITING_RESOLUTION = "AWAITING_RESOLUTION"
    COMPLETED = "COMPLETED"
    DECLINED = "DECLINED"
    NO_ANSWER = "NO_ANSWER"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_VOICE_STATUSES = frozenset({
    VoiceCallStatus.COMPLETED,
    VoiceCallStatus.DECLINED,
    VoiceCallStatus.NO_ANSWER,
    VoiceCallStatus.FAILED,
    VoiceCallStatus.CANCELLED,
})


VALID_VOICE_TRANSITIONS: dict[VoiceCallStatus, frozenset[VoiceCallStatus]] = {
    VoiceCallStatus.CALL_QUEUED: frozenset({VoiceCallStatus.CALL_INITIATED, VoiceCallStatus.FAILED, VoiceCallStatus.CANCELLED}),
    VoiceCallStatus.CALL_INITIATED: frozenset({VoiceCallStatus.RINGING, VoiceCallStatus.CONNECTED, VoiceCallStatus.FAILED, VoiceCallStatus.CANCELLED}),
    VoiceCallStatus.RINGING: frozenset({VoiceCallStatus.CONNECTED, VoiceCallStatus.NO_ANSWER, VoiceCallStatus.FAILED, VoiceCallStatus.CANCELLED}),
    VoiceCallStatus.CONNECTED: frozenset({
        VoiceCallStatus.CONVERSATION,
        VoiceCallStatus.AWAITING_RESOLUTION,
        VoiceCallStatus.COMPLETED,
        VoiceCallStatus.DECLINED,
        VoiceCallStatus.FAILED,
        VoiceCallStatus.CANCELLED,
    }),
    VoiceCallStatus.CONVERSATION: frozenset({
        VoiceCallStatus.AWAITING_RESOLUTION,
        VoiceCallStatus.COMPLETED,
        VoiceCallStatus.DECLINED,
        VoiceCallStatus.FAILED,
        VoiceCallStatus.CANCELLED,
    }),
    VoiceCallStatus.AWAITING_RESOLUTION: frozenset({VoiceCallStatus.COMPLETED, VoiceCallStatus.DECLINED, VoiceCallStatus.FAILED, VoiceCallStatus.CANCELLED}),
    VoiceCallStatus.COMPLETED: frozenset(),
    VoiceCallStatus.DECLINED: frozenset(),
    VoiceCallStatus.NO_ANSWER: frozenset(),
    VoiceCallStatus.FAILED: frozenset(),
    VoiceCallStatus.CANCELLED: frozenset(),
}


class VoiceLifecycleError(DomainError):
    pass


class VoiceTerminalStateError(VoiceLifecycleError):
    pass


def validate_voice_transition(current: str, target: VoiceCallStatus) -> None:
    try:
        current_status = VoiceCallStatus(current)
    except ValueError as exc:
        raise VoiceLifecycleError(f"unknown voice call status: {current}") from exc
    if current_status in TERMINAL_VOICE_STATUSES:
        raise VoiceTerminalStateError(f"terminal voice call cannot transition: {current_status} -> {target}")
    if target not in VALID_VOICE_TRANSITIONS[current_status]:
        raise VoiceLifecycleError(f"invalid voice call transition: {current_status} -> {target}")
