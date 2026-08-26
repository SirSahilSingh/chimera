from __future__ import annotations

from backend.app.domain import DomainError


class VoiceDomainError(DomainError):
    pass


class VoiceNotFoundError(VoiceDomainError):
    pass


class VoiceActionNotAllowedError(VoiceDomainError):
    pass


class VoiceProviderFailure(VoiceDomainError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InvalidVoiceWebhookError(VoiceDomainError):
    pass


class VoiceDuplicateError(VoiceDomainError):
    pass
