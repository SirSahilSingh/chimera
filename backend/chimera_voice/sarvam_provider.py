from __future__ import annotations

import base64
import array
import io
import json
import socket
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4
import wave


class SarvamSpeechError(RuntimeError):
    def __init__(self, code: str, message: str | None = None, *, status: int | None = None, provider_code: str | None = None) -> None:
        self.code = code
        self.message = message or code
        self.status = status
        self.provider_code = provider_code
        super().__init__(self.message)


class SarvamSpeechProvider:
    """Sarvam Saaras/Bulbul adapter for CHIMERA's telephony turn loop."""

    name = "sarvam"
    mode = "TEST"
    _audio_cache: dict[str, bytes] = {}
    _audio_lock = Lock()

    def __init__(self, api_key: str | None, *, enabled: bool = False, timeout_seconds: float = 20.0, base_url: str = "https://api.sarvam.ai", language_code: str = "hi-IN", stt_model: str = "saaras:v3", stt_mode: str = "codemix", tts_model: str = "bulbul:v3", tts_speaker: str = "shubh", mode: str | None = None) -> None:
        self.api_key = str(api_key).strip().strip('"').strip("'") if api_key else None
        self.enabled = bool(enabled) or bool(self.api_key)
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
        pcm, sample_rate = self._pcm_from_audio(audio, fallback_rate=8000)
        pcm = self._resample_pcm16(pcm, sample_rate, 16000)
        audio = self._wav(pcm, 16000)
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
        # Exotel's Voicebot applet ultimately expects raw 16-bit little-endian
        # mono PCM at 8 kHz. Request Linear16 at that rate, normalize the
        # response, and return a WAV container from this shared provider method
        # so the existing Twilio audio endpoint remains valid. The Exotel
        # stream adapter strips the WAV container immediately before sending.
        primary_body = {
            "text": text,
            "inputs": [text],
            "model": self.tts_model,
            "speaker": self.tts_speaker,
            "language_code": self.language_code,
            "target_language_code": self.language_code,
            "speech_sample_rate": 8000,
            "output_audio_codec": "linear16",
            "pace": 1.0,
            "temperature": 0.4,
        }
        request = Request(
            f"{self.base_url}/text-to-speech",
            data=json.dumps(primary_body).encode("utf-8"),
            headers={"api-subscription-key": self.api_key, "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            payload = self._request(request)
        except SarvamSpeechError as error:
            # If rejected due to schema/field incompatibility (e.g. 400/422), fallback to minimal bulbul schema
            if error.status in {400, 422}:
                fallback_body = {
                    "inputs": [text],
                    "target_language_code": self.language_code,
                    "speaker": self.tts_speaker,
                    "model": self.tts_model,
                }
                fallback_request = Request(
                    f"{self.base_url}/text-to-speech",
                    data=json.dumps(fallback_body).encode("utf-8"),
                    headers={"api-subscription-key": self.api_key, "Content-Type": "application/json", "Accept": "application/json"},
                    method="POST",
                )
                try:
                    payload = self._request(fallback_request)
                except SarvamSpeechError:
                    raise error from None
            else:
                raise

        raw_b64 = None
        if isinstance(payload, dict):
            audios = payload.get("audios")
            if isinstance(audios, list) and audios:
                raw_b64 = audios[0]
            elif isinstance(audios, str):
                raw_b64 = audios
            else:
                raw_b64 = payload.get("audio") or payload.get("audio_content")

        if not raw_b64 or not isinstance(raw_b64, str):
            raise SarvamSpeechError("provider_invalid_response", "Sarvam returned no audio payload.")

        try:
            audio = base64.b64decode(raw_b64)
        except (TypeError, ValueError) as exc:
            raise SarvamSpeechError("provider_invalid_response", "Sarvam returned invalid base64 audio.") from exc

        pcm, sample_rate = self._pcm_from_audio(audio, fallback_rate=8000)
        pcm = self._resample_pcm16(pcm, sample_rate, 8000)
        return self._wav(pcm, 8000)

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
            raise SarvamSpeechError("provider_timeout", "Sarvam request timed out.") from None
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            provider_code, message = self._provider_error(body)
            normalized = f"{provider_code or ''} {message or ''}".casefold()
            if exc.code == 402 or provider_code in {"insufficient_quota_error", "insufficient_credits_error"} or any(term in normalized for term in ("insufficient credit", "credits exhausted", "no credits", "quota exhausted")):
                raise SarvamSpeechError("sarvam_credits_exhausted", message or "Sarvam credits are exhausted.", status=exc.code, provider_code=provider_code) from None
            if exc.code in {401, 403}:
                raise SarvamSpeechError("sarvam_invalid_credentials", message or "Sarvam rejected the API key.", status=exc.code, provider_code=provider_code) from None
            if exc.code == 429:
                raise SarvamSpeechError("sarvam_rate_limited", message or "Sarvam rate limit exceeded.", status=exc.code, provider_code=provider_code) from None
            raise SarvamSpeechError("sarvam_provider_error", message or "Sarvam request failed.", status=exc.code, provider_code=provider_code) from None
        except (URLError, OSError, ValueError):
            raise SarvamSpeechError("sarvam_provider_error", "Sarvam returned an invalid or unreachable response.") from None

    @staticmethod
    def _provider_error(body: str) -> tuple[str | None, str | None]:
        try:
            payload = json.loads(body)
        except (TypeError, ValueError):
            text = " ".join(body.split())
            return None, text[:255] if text else None
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            return str(code)[:96] if code else None, str(message)[:255] if message else None
        if isinstance(payload, dict):
            code = payload.get("code")
            message = payload.get("message") or payload.get("detail")
            return str(code)[:96] if code else None, str(message)[:255] if message else None
        return None, None

    @classmethod
    def _pcm_from_audio(cls, raw: bytes, *, fallback_rate: int) -> tuple[bytes, int]:
        """Decode Sarvam audio into mono PCM and preserve its actual sample rate."""
        if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
            try:
                with wave.open(io.BytesIO(raw), "rb") as wav_file:
                    channels = wav_file.getnchannels()
                    width = wav_file.getsampwidth()
                    rate = wav_file.getframerate()
                    if width != 2 or channels not in (1, 2):
                        raise SarvamSpeechError("provider_invalid_response", f"Unsupported Sarvam WAV: channels={channels}, width={width}.")
                    pcm = wav_file.readframes(wav_file.getnframes())
                if channels == 2:
                    pcm = cls._downmix_stereo(pcm)
                return pcm, rate
            except (wave.Error, EOFError) as exc:
                raise SarvamSpeechError("provider_invalid_response", "Sarvam returned a malformed WAV payload.") from exc
        return raw, fallback_rate

    @staticmethod
    def _downmix_stereo(pcm: bytes) -> bytes:
        samples = array.array("h")
        samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
        mono = array.array("h")
        for index in range(0, len(samples) - 1, 2):
            mono.append(max(-32768, min(32767, (samples[index] + samples[index + 1]) // 2)))
        return mono.tobytes()

    @staticmethod
    def _resample_pcm16(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
        if not pcm or from_rate == to_rate:
            return pcm
        samples = array.array("h")
        samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
        if len(samples) < 2 or from_rate <= 0 or to_rate <= 0:
            return pcm
        output_length = max(1, round(len(samples) * to_rate / from_rate))
        output = array.array("h")
        ratio = from_rate / to_rate
        for index in range(output_length):
            source = index * ratio
            left = min(int(source), len(samples) - 1)
            right = min(left + 1, len(samples) - 1)
            fraction = source - left
            value = round(samples[left] * (1.0 - fraction) + samples[right] * fraction)
            output.append(max(-32768, min(32767, value)))
        return output.tobytes()

    @staticmethod
    def _wav(pcm: bytes, sample_rate: int) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)
        return output.getvalue()
