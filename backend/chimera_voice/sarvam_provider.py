from __future__ import annotations

import base64
import json
import socket
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


class SarvamSpeechError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SarvamSpeechProvider:
    """Sarvam Saaras/Bulbul adapter for CHIMERA's telephony turn loop."""

    name = "sarvam"
    mode = "TEST"
    _audio_cache: dict[str, bytes] = {}
    _audio_lock = Lock()

    def __init__(self, api_key: str | None, *, enabled: bool, timeout_seconds: float = 20.0, base_url: str = "https://api.sarvam.ai", language_code: str = "hi-IN", stt_model: str = "saaras:v3", stt_mode: str = "codemix", tts_model: str = "bulbul:v3", tts_speaker: str = "shubh", mode: str | None = None) -> None:
        self.api_key = api_key
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")
        self.language_code = language_code
        self.stt_model = stt_model
        self.stt_mode = stt_mode
        self.tts_model = tts_model
        self.tts_speaker = tts_speaker
        if mode:
            self.mode = mode.upper()

    def _require_configuration(self) -> None:
        if not self.enabled or not self.api_key:
            raise SarvamSpeechError("provider_not_configured")

    def transcribe(self, audio: bytes, *, content_type: str = "audio/wav") -> str:
        self._require_configuration()
        if not audio:
            raise SarvamSpeechError("empty_recording")
        boundary = f"----chimera-{uuid4().hex}"
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"recording.wav\"\r\nContent-Type: {content_type}\r\n\r\n".encode("utf-8") + audio + b"\r\n",
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{self.stt_model}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"mode\"\r\n\r\n{self.stt_mode}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"language_code\"\r\n\r\n{self.language_code}\r\n".encode("utf-8"),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
        request = Request(f"{self.base_url}/speech-to-text", data=b"".join(parts), headers={"api-subscription-key": self.api_key, "Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"}, method="POST")
        payload = self._request(request)
        transcript = payload.get("transcript")
        if not isinstance(transcript, str) or not transcript.strip():
            raise SarvamSpeechError("provider_invalid_response")
        return transcript.strip()

    def synthesize(self, text: str) -> bytes:
        self._require_configuration()
        body = json.dumps({"text": text, "model": self.tts_model, "speaker": self.tts_speaker, "language_code": self.language_code, "speech_sample_rate": 8000, "output_audio_codec": "wav", "pace": 1.0, "temperature": 0.4}).encode("utf-8")
        request = Request(f"{self.base_url}/text-to-speech", data=body, headers={"api-subscription-key": self.api_key, "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        payload = self._request(request)
        try:
            return base64.b64decode(payload["audios"][0])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise SarvamSpeechError("provider_invalid_response") from exc

    def audio_token(self, text: str) -> str:
        audio = self.synthesize(text)
        token = uuid4().hex
        with self._audio_lock:
            self._audio_cache[token] = audio
            if len(self._audio_cache) > 128:
                self._audio_cache.pop(next(iter(self._audio_cache)))
        return token

    @classmethod
    def audio_bytes(cls, token: str) -> bytes | None:
        with cls._audio_lock:
            return cls._audio_cache.get(token)

    def verify_connectivity(self) -> None:
        """Validate configuration without generating billable speech."""
        self._require_configuration()

    def _request(self, request: Request) -> dict:
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout):
            raise SarvamSpeechError("provider_timeout") from None
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise SarvamSpeechError("invalid_credentials") from None
            if exc.code == 429:
                raise SarvamSpeechError("rate_limited") from None
            raise SarvamSpeechError("provider_request_failed") from None
        except (URLError, OSError, ValueError):
            raise SarvamSpeechError("provider_request_failed") from None
