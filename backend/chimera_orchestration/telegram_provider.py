from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class EscalationNotificationResult:
    provider: str
    provider_reference: str
    status: str


class TelegramEscalationProvider:
    """Free operator-notification adapter using the Telegram Bot API."""

    name = "telegram"
    mode = "LIVE"

    def __init__(self, bot_token: str | None, chat_id: str | None, *, enabled: bool, timeout_seconds: float = 10.0, mode: str | None = None) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        if mode:
            self.mode = mode.upper()

    def _require_configuration(self) -> None:
        if not self.enabled or not self.bot_token or not self.chat_id:
            raise RuntimeError("provider_not_configured")

    def notify(self, escalation, reason: str) -> EscalationNotificationResult:
        self._require_configuration()
        context = escalation.context_json
        amount = int(context.get("amount_paise", 0)) / 100
        text = (
            f"CHIMERA escalation\n"
            f"Priority: P{escalation.priority}\n"
            f"Case: {escalation.recovery_case_id}\n"
            f"Customer: {context.get('customer_id', 'unknown')}\n"
            f"Amount: INR {amount:.2f}\n"
            f"Reason: {reason}"
        )
        payload = self._request("sendMessage", {"chat_id": self.chat_id, "text": text})
        try:
            reference = str(payload["result"]["message_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("provider_invalid_response") from exc
        return EscalationNotificationResult(self.name, reference[:255], "SENT")

    def verify_connectivity(self) -> None:
        self._require_configuration()
        self._request("getMe", {})

    def _request(self, method: str, fields: dict) -> dict:
        body = urlencode(fields).encode("utf-8")
        request = Request(f"https://api.telegram.org/bot{self.bot_token}/{method}", data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("ok"):
                raise RuntimeError("provider_request_failed")
            return payload
        except RuntimeError:
            raise
        except (TimeoutError, socket.timeout):
            raise RuntimeError("provider_timeout") from None
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError("invalid_credentials") from None
            raise RuntimeError("provider_request_failed") from None
        except (URLError, OSError, ValueError):
            raise RuntimeError("provider_request_failed") from None
