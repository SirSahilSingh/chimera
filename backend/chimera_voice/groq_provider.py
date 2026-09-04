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

        return f"""You are CHIMERA's courteous, conversational AI Voice Recovery Agent calling an Indian customer regarding an incomplete payment.

Case Facts:
- Amount: {amount_inr} {context.currency}
- Payment Method: {context.payment_method}
- Failure Reason: {context.failure_reason}
- {incident_info}

CRITICAL CONVERSATIONAL RULES:
1. Speak in warm, natural, friendly conversational Hinglish (blend of Hindi and English, written in natural Hindi script or Hinglish).
2. Keep replies VERY CONCISE: 1 to 2 short sentences (maximum 20-30 words). Never give long speeches or monologues.
3. If customer agrees, says 'hmm sahi hai', 'haan', 'theek hai', 'accha', 'ok', or asks for payment link:
   Politely affirm and ask if you should send the direct payment link on their WhatsApp right now.
4. If customer asks ANY questions (e.g. 'किसका payment है?', 'क्यों fail हुआ?', 'क्या समस्या थी?', 'कैसे pay करूँ?', 'kya call hai?'):
   Answer directly, helpfully and accurately using the Case Facts ({amount_inr} via {context.payment_method} due to {context.failure_reason}), then ask if they'd like the payment link sent to WhatsApp.
5. If customer says they will pay later: acknowledge politely and say we have noted the retry preference.
6. If customer says they already paid: thank them and explain our finance team will verify the payment status.
7. If customer declines or says wrong number: politely apologize and close the call.
8. HARD SAFETY: NEVER ask for card numbers, OTP, CVV, passwords, or UPI PIN.
"""

    def generate_response(
        self,
        context: VoiceContext,
        history: list[dict[str, str]],
        user_text: str,
    ) -> str | None:
        if not self.is_configured:
            logger.warning("GroqVoiceAgent is not configured (missing GROQ_API_KEY)")
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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                pass
            logger.warning("Groq API HTTP error %s: %s | %s", exc.code, exc.reason, body)
            return None
        except (URLError, TimeoutError, KeyError, Exception) as exc:
            logger.warning("Groq API request failed: %s", exc)
            return None
