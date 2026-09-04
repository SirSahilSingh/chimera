from __future__ import annotations

import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .schemas import VoiceContext

logger = logging.getLogger(__name__)


class GroqVoiceAgent:
    """Ultra-low-latency Hinglish dialogue reasoning powered by Groq."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str | None = None,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_seconds: float = 6.0,
    ) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _build_system_prompt(self, context: VoiceContext) -> str:
        amount_inr = f"₹{context.payment_amount_paise / 100:,.2f}"
        incident_info = (
            "Note: An upstream banking incident flag is recorded for this payment."
            if context.incident_flag
            else "No bank outage flag."
        )

        return f"""You are CHIMERA's courteous, professional AI Voice Recovery Agent calling an Indian customer regarding an incomplete payment.

Case Facts:
- Amount: {amount_inr} {context.currency}
- Payment Method: {context.payment_method}
- Failure Reason: {context.failure_reason}
- {incident_info}

CRITICAL PHONE CALL RULES:
1. Speak in natural, friendly, conversational Hinglish (blend of Hindi and English, written in natural Hindi script or Hinglish).
2. Keep responses VERY SHORT: exactly 1 or 2 brief sentences (maximum 25-35 words). This is a real-time phone call. Do not give long lectures.
3. If customer agrees or asks for a payment link: affirm politely and state that a secure payment link will be sent to their WhatsApp/SMS.
4. If customer says they will pay later: acknowledge politely and say we have noted the retry preference.
5. If customer says they already paid: thank them and explain that our finance team will verify the bank status.
6. If customer declines or says wrong number: politely apologize and say we will close the call.
7. HARD SAFETY: NEVER ask for card numbers, OTP, CVV, or UPI PIN. Never claim money is recovered until the gateway confirms it.
"""

    def generate_response(
        self,
        context: VoiceContext,
        history: list[dict[str, str]],
        user_text: str,
    ) -> str | None:
        if not self.is_configured:
            return None

        system_instruction = self._build_system_prompt(context)
        messages = [{"role": "system", "content": system_instruction}]

        # Include up to last 6 turns for context
        for turn in history[-6:]:
            role = "assistant" if turn.get("speaker") == "agent" else "user"
            content = turn.get("text", "")
            if content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 80,
            "top_p": 0.9,
        }

        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key.strip()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]["message"]["content"]
            clean_text = choice.strip().strip('"')
            return clean_text
        except HTTPError as exc:
            logger.warning("Groq API HTTP error %s: %s", exc.code, exc.reason)
            return None
        except (URLError, TimeoutError, KeyError, Exception) as exc:
            logger.warning("Groq API request failed: %s", exc)
            return None
