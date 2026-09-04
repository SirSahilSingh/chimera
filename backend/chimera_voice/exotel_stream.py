from __future__ import annotations

import asyncio
import base64
import io
import json
import struct
import wave
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .errors import VoiceDomainError
from .sarvam_provider import SarvamSpeechError, SarvamSpeechProvider


class ExotelStreamSession:
    """Bridge Exotel AgentStream audio to Sarvam and the controlled voice service."""

    _CHUNK_BYTES = 3200  # 100 ms of 8 kHz, 16-bit mono PCM.
    _SILENCE_FLUSH_MS = 800
    _MAX_TURN_MS = 12000

    def __init__(self, websocket: WebSocket, *, voice_service, speech_provider: SarvamSpeechProvider, intervention_id: str | None) -> None:
        self.websocket = websocket
        self.voice_service = voice_service
        self.speech_provider = speech_provider
        self.intervention_id = intervention_id
        self.stream_sid: str | None = None
        self.sequence_number = 0
        self.audio_buffer = bytearray()
        self.speech_started = False
        self.silence_ms = 0
        self.elapsed_ms = 0
        self.close_after_mark = False
        self.output_timestamp_ms = 0

    async def run(self) -> None:
        await self.websocket.accept()
        try:
            while True:
                message = await self.websocket.receive_json()
                event = str(message.get("event", "")).casefold()
                if event == "start":
                    await self._handle_start(message)
                elif event == "media":
                    await self._handle_media(message)
                elif event == "dtmf":
                    await self._handle_dtmf(message)
                elif event == "stop":
                    await self._flush_audio()
                    return
                elif event == "mark":
                    if self.close_after_mark:
                        return
                elif event in {"connected", "clear"}:
                    continue
        except WebSocketDisconnect:
            return
        except SarvamSpeechError as exc:
            await asyncio.to_thread(
                self.voice_service.exotel_stream_failed,
                self.intervention_id,
                stage="sarvam",
                code=exc.code,
                message=exc.message,
            )
            await self._close_with_error()
        except (VoiceDomainError, ValueError, KeyError) as exc:
            # The call status callback remains the source of telephony truth. Close
            # the media stream cleanly when the bridge cannot continue, but retain
            # the reason in the persisted journey for operator diagnosis.
            await asyncio.to_thread(
                self.voice_service.exotel_stream_failed,
                self.intervention_id,
                stage="bridge",
                code="voice_stream_failure",
                message=str(exc),
            )
            await self._close_with_error()

    async def _handle_start(self, message: dict[str, Any]) -> None:
        start = message.get("start") if isinstance(message.get("start"), dict) else message
        self.stream_sid = (
            message.get("stream_sid")
            or message.get("streamSid")
            or message.get("stream sid")
            or start.get("stream_sid")
            or start.get("streamSid")
            or start.get("stream sid")
        )
        call_sid = (
            message.get("call_sid")
            or message.get("callSid")
            or message.get("CallSid")
            or start.get("call_sid")
            or start.get("callSid")
            or start.get("CallSid")
            or start.get("sid")
            or start.get("Sid")
        )
        if not self.intervention_id:
            custom = (
                start.get("custom_parameters")
                or start.get("customParameters")
                or start.get("custom parameters")
                or {}
            )
            if isinstance(custom, dict):
                self.intervention_id = (
                    custom.get("intervention_id")
                    or custom.get("interventionId")
                    or custom.get("intervention id")
                )

        if not self.intervention_id and call_sid:
            try:
                call = await asyncio.to_thread(self.voice_service.get_call_for_provider_reference, str(call_sid).strip())
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
            raise ValueError("Exotel stream is missing intervention_id")

        await asyncio.to_thread(self.voice_service.exotel_stream_opened, self.intervention_id, self.stream_sid)
        opening = await asyncio.to_thread(self.voice_service.exotel_opening, self.intervention_id)
        audio = await asyncio.to_thread(self.speech_provider.synthesize, opening)
        await self._send_audio(audio)

    async def _handle_dtmf(self, message: dict[str, Any]) -> None:
        dtmf = message.get("dtmf") if isinstance(message.get("dtmf"), dict) else {}
        digit = str(dtmf.get("digit", ""))
        if digit in {"1", "2"} and self.intervention_id:
            text = "yes" if digit == "1" else "later"
            await self._respond(text)

    async def _handle_media(self, message: dict[str, Any]) -> None:
        media = message.get("media") if isinstance(message.get("media"), dict) else {}
        payload = media.get("payload")
        if not isinstance(payload, str):
            return
        try:
            chunk = base64.b64decode(payload, validate=True)
        except (ValueError, TypeError):
            return
        if not chunk:
            return
        self.audio_buffer.extend(chunk)
        duration_ms = max(1, len(chunk) // 16)
        self.elapsed_ms += duration_ms
        speaking = self._has_voice(chunk)
        if speaking:
            self.speech_started = True
            self.silence_ms = 0
        elif self.speech_started:
            self.silence_ms += duration_ms
        if (self.speech_started and self.silence_ms >= self._SILENCE_FLUSH_MS) or self.elapsed_ms >= self._MAX_TURN_MS:
            await self._flush_audio()

    async def _flush_audio(self) -> None:
        if not self.speech_started or len(self.audio_buffer) < 640:
            self.audio_buffer.clear()
            self.speech_started = False
            self.silence_ms = 0
            self.elapsed_ms = 0
            return
        audio = self._wav(bytes(self.audio_buffer))
        self.audio_buffer.clear()
        self.speech_started = False
        self.silence_ms = 0
        self.elapsed_ms = 0
        transcript = await asyncio.to_thread(self.speech_provider.transcribe, audio, content_type="audio/wav")
        if transcript and self.intervention_id:
            await self._respond(transcript)

    async def _respond(self, transcript: str) -> None:
        response, should_end = await asyncio.to_thread(self.voice_service.handle_exotel_transcript, self.intervention_id, transcript)
        self.close_after_mark = should_end
        await self._send_audio(await asyncio.to_thread(self.speech_provider.synthesize, response))

    async def _send_audio(self, audio: bytes) -> None:
        pcm = self._pcm_from_wav(audio)
        if not pcm or not self.stream_sid:
            return
        chunk_size = 1600  # 100 ms of 8 kHz, 16-bit mono PCM
        for offset in range(0, len(pcm), chunk_size):
            chunk = pcm[offset : offset + chunk_size]
            if len(chunk) % 320:
                chunk += b"\x00" * (320 - (len(chunk) % 320))
            if not chunk:
                continue
            self.sequence_number += 1
            try:
                await self.websocket.send_json({
                    "event": "media",
                    "stream_sid": self.stream_sid,
                    "sequence_number": self.sequence_number,
                    "media": {
                        "chunk": self.sequence_number,
                        "timestamp": str(self.output_timestamp_ms),
                        "payload": base64.b64encode(chunk).decode("ascii"),
                    },
                })
            except Exception:
                return
            self.output_timestamp_ms += len(chunk) // 16
            if offset >= chunk_size * 2:
                await asyncio.sleep(0.08)
        self.sequence_number += 1
        try:
            await self.websocket.send_json({
                "event": "mark",
                "stream_sid": self.stream_sid,
                "sequence_number": self.sequence_number,
                "mark": {"name": f"chimera-audio-{self.sequence_number}"},
            })
        except Exception:
            return

    async def _close_with_error(self) -> None:
        try:
            await self.websocket.close(code=1011, reason="voice bridge failure")
        except Exception:
            return

    @staticmethod
    def _has_voice(chunk: bytes) -> bool:
        samples = struct.iter_unpack("<h", chunk[: len(chunk) - (len(chunk) % 2)])
        peak = max((abs(sample[0]) for sample in samples), default=0)
        return peak >= 500

    @staticmethod
    def _wav(pcm: bytes) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(8000)
            wav_file.writeframes(pcm)
        return output.getvalue()

    @staticmethod
    def _pcm_from_wav(audio: bytes) -> bytes:
        if not audio.startswith(b"RIFF"):
            return audio
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav_file:
                return wav_file.readframes(wav_file.getnframes())
        except (wave.Error, EOFError):
            return b""
