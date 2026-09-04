from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import struct
import wave
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .errors import VoiceDomainError
from .groq_provider import GroqVoiceAgent
from .sarvam_provider import SarvamSpeechError, SarvamSpeechProvider

logger = logging.getLogger(__name__)


class VobizStreamSession:
    """Bridge Vobiz bidirectional WebSocket audio to Sarvam (Saaras/Bulbul) and Groq."""

    _SAMPLE_RATE = 16000
    _BYTES_PER_MS = 32  # 16 kHz * 2 bytes/sample (16-bit mono) / 1000 ms
    _SILENCE_FLUSH_MS = 750
    _MAX_TURN_MS = 10000
    _ENERGY_THRESHOLD = 350

    def __init__(
        self,
        websocket: WebSocket,
        *,
        voice_service,
        speech_provider: SarvamSpeechProvider,
        intervention_id: str | None = None,
        groq_agent: GroqVoiceAgent | None = None,
    ) -> None:
        self.websocket = websocket
        self.voice_service = voice_service
        self.speech_provider = speech_provider
        self.intervention_id = intervention_id
        self.groq_agent = groq_agent or GroqVoiceAgent()
        self.stream_id: str | None = None
        self.call_id: str | None = None
        self.audio_buffer = bytearray()
        self.speech_started = False
        self.silence_ms = 0
        self.elapsed_ms = 0
        self.is_playing = False
        self.close_after_playback = False

    async def run(self) -> None:
        await self.websocket.accept()
        try:
            while True:
                message = await self.websocket.receive_json()
                event = str(message.get("event", "")).strip()

                if event == "start":
                    await self._handle_start(message)
                elif event == "media":
                    await self._handle_media(message)
                elif event == "playedStream":
                    self.is_playing = False
                    if self.close_after_playback:
                        return
                elif event in {"stop", "disconnect", "close"}:
                    await self._flush_audio()
                    return
        except WebSocketDisconnect:
            logger.info("Vobiz WebSocket disconnected for stream %s", self.stream_id)
            return
        except SarvamSpeechError as exc:
            logger.error("Sarvam speech error during Vobiz stream: %s", exc)
            if self.intervention_id:
                await asyncio.to_thread(
                    self.voice_service.vobiz_stream_failed,
                    self.intervention_id,
                    stage="sarvam",
                    code=exc.code,
                    message=exc.message,
                )
            await self._close_with_error()
        except (VoiceDomainError, ValueError, KeyError, Exception) as exc:
            logger.error("Vobiz voice stream failure: %s", exc)
            if self.intervention_id:
                await asyncio.to_thread(
                    self.voice_service.vobiz_stream_failed,
                    self.intervention_id,
                    stage="bridge",
                    code="voice_stream_failure",
                    message=str(exc),
                )
            await self._close_with_error()

    async def _handle_start(self, message: dict[str, Any]) -> None:
        self.stream_id = message.get("streamId") or message.get("stream_id") or message.get("streamSid")
        self.call_id = message.get("callId") or message.get("call_id") or message.get("callSid")

        # Associate intervention_id if not present from query params
        if not self.intervention_id and self.call_id:
            try:
                call = await asyncio.to_thread(self.voice_service.get_call_for_provider_reference, str(self.call_id).strip())
                self.intervention_id = call.intervention_id
            except Exception:
                pass

        if not self.intervention_id:
            try:
                latest_call = await asyncio.to_thread(self.voice_service.get_latest_active_call)
                if latest_call is not None:
                    self.intervention_id = latest_call.intervention_id
            except Exception:
                pass

        if not self.intervention_id:
            logger.warning("Vobiz stream started without intervention_id for call %s", self.call_id)
            return

        await asyncio.to_thread(self.voice_service.vobiz_stream_opened, self.intervention_id, self.stream_id)
        opening_text = await asyncio.to_thread(self.voice_service.vobiz_opening, self.intervention_id)
        audio_wav = await asyncio.to_thread(self.speech_provider.synthesize, opening_text, sample_rate=self._SAMPLE_RATE)
        await self._send_audio(audio_wav)

    async def _handle_media(self, message: dict[str, Any]) -> None:
        media = message.get("media") if isinstance(message.get("media"), dict) else {}
        payload = media.get("payload")
        if not isinstance(payload, str) or not payload:
            return

        try:
            chunk = base64.b64decode(payload, validate=True)
        except (ValueError, TypeError):
            return

        if not chunk:
            return

        self.audio_buffer.extend(chunk)
        chunk_ms = max(1, len(chunk) // self._BYTES_PER_MS)
        self.elapsed_ms += chunk_ms

        speaking = self._has_voice(chunk)
        if speaking:
            # Barge-in: if bot was speaking and caller interrupts, stop playback
            if self.is_playing:
                await self._clear_audio()
                self.is_playing = False
            self.speech_started = True
            self.silence_ms = 0
        elif self.speech_started:
            self.silence_ms += chunk_ms

        if (self.speech_started and self.silence_ms >= self._SILENCE_FLUSH_MS) or self.elapsed_ms >= self._MAX_TURN_MS:
            await self._flush_audio()

    async def _clear_audio(self) -> None:
        if not self.stream_id:
            return
        try:
            await self.websocket.send_json({
                "event": "clearAudio",
                "streamId": self.stream_id,
            })
        except Exception:
            pass

    async def _flush_audio(self) -> None:
        if not self.speech_started or len(self.audio_buffer) < 1280:
            self.audio_buffer.clear()
            self.speech_started = False
            self.silence_ms = 0
            self.elapsed_ms = 0
            return

        audio_wav = self._wav(bytes(self.audio_buffer))
        self.audio_buffer.clear()
        self.speech_started = False
        self.silence_ms = 0
        self.elapsed_ms = 0

        transcript = await asyncio.to_thread(self.speech_provider.transcribe, audio_wav, content_type="audio/wav")
        if transcript and self.intervention_id:
            await self._respond(transcript)

    async def _respond(self, transcript: str) -> None:
        response_text: str | None = None
        should_end = False

        # Attempt ultra-low-latency Groq Hinglish LLM first
        if self.groq_agent and self.groq_agent.is_configured:
            try:
                context = await asyncio.to_thread(self.voice_service.get_voice_context, self.intervention_id)
                history = await asyncio.to_thread(self.voice_service.get_recent_history, self.intervention_id)
                response_text = await asyncio.to_thread(
                    self.groq_agent.generate_response, context, history, transcript
                )
            except Exception as exc:
                logger.warning("Groq reasoning failed, falling back to VoiceService: %s", exc)

        if response_text:
            # Record the turn and check for termination
            should_end = await asyncio.to_thread(
                self.voice_service.record_vobiz_turn,
                self.intervention_id,
                transcript,
                response_text,
            )
        else:
            response_text, should_end = await asyncio.to_thread(
                self.voice_service.handle_vobiz_transcript, self.intervention_id, transcript
            )

        self.close_after_playback = should_end
        audio_wav = await asyncio.to_thread(self.speech_provider.synthesize, response_text, sample_rate=self._SAMPLE_RATE)
        await self._send_audio(audio_wav)

    async def _send_audio(self, audio_wav: bytes) -> None:
        pcm = self._pcm_from_wav(audio_wav)
        if not pcm or not self.stream_id:
            return

        self.is_playing = True
        chunk_size = 3200  # 100 ms of 16 kHz, 16-bit mono PCM (3200 bytes)

        for offset in range(0, len(pcm), chunk_size):
            chunk = pcm[offset : offset + chunk_size]
            if len(chunk) % 2 != 0:
                chunk += b"\x00"
            if not chunk:
                continue

            try:
                await self.websocket.send_json({
                    "event": "playAudio",
                    "streamId": self.stream_id,
                    "media": {
                        "contentType": "audio/x-l16",
                        "sampleRate": self._SAMPLE_RATE,
                        "payload": base64.b64encode(chunk).decode("ascii"),
                    },
                })
            except Exception:
                return

            if offset >= chunk_size * 2:
                await asyncio.sleep(0.08)

    def _has_voice(self, pcm: bytes) -> bool:
        """Measure RMS energy of 16-bit mono PCM."""
        if len(pcm) < 4:
            return False
        count = len(pcm) // 2
        try:
            samples = struct.unpack(f"<{count}h", pcm[: count * 2])
        except struct.error:
            return False
        total_energy = sum(s * s for s in samples)
        rms = int((total_energy / count) ** 0.5)
        return rms > self._ENERGY_THRESHOLD

    def _wav(self, pcm: bytes) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self._SAMPLE_RATE)
            wav_file.writeframes(pcm)
        return output.getvalue()

    @staticmethod
    def _pcm_from_wav(audio_bytes: bytes) -> bytes:
        if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
            try:
                with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                    return wav_file.readframes(wav_file.getnframes())
            except Exception:
                pass
        return audio_bytes

    async def _close_with_error(self) -> None:
        try:
            await self.websocket.close(code=1011, reason="voice stream failure")
        except Exception:
            pass
