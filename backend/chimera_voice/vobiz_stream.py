from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import struct
import uuid
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
    _SILENCE_FLUSH_MS = 800
    _MIN_SPEECH_MS = 250
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
        self.is_processing = False
        self.close_after_playback = False
        self._tasks: set[asyncio.Task] = set()

    async def run(self) -> None:
        await self.websocket.accept()
        logger.info("Vobiz WebSocket connected: intervention_id=%s", self.intervention_id)
        try:
            while True:
                text = await self.websocket.receive_text()
                try:
                    message = json.loads(text)
                except Exception:
                    continue

                event = str(message.get("event", "")).strip()

                if event == "start":
                    await self._handle_start(message)
                elif event == "media":
                    await self._handle_media(message)
                elif event in {"playedStream", "clearedAudio"}:
                    self.is_playing = False
                    if self.close_after_playback:
                        await asyncio.sleep(0.8)
                        if self.intervention_id:
                            try:
                                await asyncio.to_thread(self.voice_service.vobiz_call_completed, self.intervention_id, reason="playback_resolution_complete")
                            except Exception as exc:
                                logger.warning("Failed to mark call complete after playback: %s", exc)
                        try:
                            await self.websocket.close()
                        except Exception:
                            pass
                        return
                elif event in {"stop", "hangup", "disconnect", "close"}:
                    logger.info("Vobiz stream terminated by carrier: event=%s", event)
                    if self.intervention_id:
                        try:
                            await asyncio.to_thread(self.voice_service.vobiz_call_completed, self.intervention_id, reason=f"carrier_event_{event}")
                        except Exception as exc:
                            logger.warning("Failed to mark call complete on %s: %s", event, exc)
                    return
        except WebSocketDisconnect:
            logger.info("Vobiz WebSocket disconnected for stream %s", self.stream_id)
            if self.intervention_id:
                try:
                    await asyncio.to_thread(self.voice_service.vobiz_call_completed, self.intervention_id, reason="websocket_disconnect")
                except Exception as exc:
                    logger.warning("Failed to mark call complete on disconnect: %s", exc)
            return
        except Exception as exc:
            logger.exception("Vobiz voice stream failure: %s", exc)
            if self.intervention_id:
                try:
                    await asyncio.to_thread(
                        self.voice_service.vobiz_stream_failed,
                        self.intervention_id,
                        stage="bridge",
                        code="voice_stream_failure",
                        message=str(exc),
                    )
                except Exception:
                    pass
            await self._close_with_error()
        finally:
            await self._cleanup()

    async def _handle_start(self, message: dict[str, Any]) -> None:
        start_data = message.get("start") if isinstance(message.get("start"), dict) else {}
        self.stream_id = (
            message.get("streamId")
            or start_data.get("streamId")
            or message.get("stream_id")
            or message.get("streamSid")
        )
        self.call_id = (
            message.get("callId")
            or start_data.get("callId")
            or start_data.get("callUUID")
            or message.get("call_id")
            or message.get("callSid")
        )

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

        logger.info("Vobiz stream started: call_id=%s stream_id=%s intervention_id=%s", self.call_id, self.stream_id, self.intervention_id)

        if self.intervention_id:
            try:
                await asyncio.to_thread(self.voice_service.vobiz_stream_opened, self.intervention_id, self.stream_id)
            except Exception as exc:
                logger.warning("Failed to record stream opened: %s", exc)

        # Spawn greeting in background task so WebSocket receive loop is NEVER blocked
        self._spawn(self._play_greeting())

    async def _play_greeting(self) -> None:
        try:
            if not self.intervention_id:
                opening_text = "नमस्ते, मैं Chimera Payments से बात कर रहा हूँ। क्या मेरी बात Rohit से हो रही है?"
            else:
                opening_text = await asyncio.to_thread(self.voice_service.vobiz_opening, self.intervention_id)

            logger.info("Synthesizing greeting for intervention %s: %s", self.intervention_id, opening_text)
            audio_wav = await asyncio.to_thread(self.speech_provider.synthesize, opening_text, sample_rate=self._SAMPLE_RATE)
            await self._send_audio(audio_wav)
        except Exception as exc:
            logger.exception("Failed to synthesize or play greeting: %s", exc)

    async def _handle_media(self, message: dict[str, Any]) -> None:
        # CRITICAL: Ignore microphone input while bot is speaking or processing.
        # This prevents acoustic echo from the phone speaker leaking into the mic
        # and cutting off the agent mid-sentence.
        if self.is_playing or self.is_processing:
            return

        media = message.get("media") if isinstance(message.get("media"), dict) else {}
        if media.get("track") not in {None, "inbound"}:
            return

        payload = media.get("payload")
        if not isinstance(payload, str) or not payload:
            return

        try:
            chunk = base64.b64decode(payload, validate=True)
        except (ValueError, TypeError):
            return

        if not chunk or len(chunk) % 2 != 0:
            return

        chunk_ms = max(1, len(chunk) // self._BYTES_PER_MS)
        speaking = self._has_voice(chunk)

        if speaking:
            self.speech_started = True
            self.silence_ms = 0
            self.audio_buffer.extend(chunk)
            self.elapsed_ms += chunk_ms
        elif self.speech_started:
            self.silence_ms += chunk_ms
            self.audio_buffer.extend(chunk)
            self.elapsed_ms += chunk_ms

        if (self.speech_started and self.silence_ms >= self._SILENCE_FLUSH_MS) or self.elapsed_ms >= self._MAX_TURN_MS:
            if self.elapsed_ms >= self._MIN_SPEECH_MS and len(self.audio_buffer) >= 3200:
                audio_to_process = bytes(self.audio_buffer)
                self._reset_vad()
                self.is_processing = True
                self._spawn(self._process_utterance(audio_to_process))
            else:
                self._reset_vad()

    def _reset_vad(self) -> None:
        self.audio_buffer.clear()
        self.speech_started = False
        self.silence_ms = 0
        self.elapsed_ms = 0

    async def _process_utterance(self, pcm_bytes: bytes) -> None:
        try:
            audio_wav = self._wav(pcm_bytes)
            transcript: str | None = None
            try:
                transcript = await asyncio.to_thread(self.speech_provider.transcribe, audio_wav, content_type="audio/wav")
            except Exception as exc:
                logger.info("Speech transcription skipped (noise or silence): %s", exc)
                return

            if not transcript or not transcript.strip():
                return

            clean_text = transcript.strip()
            logger.info("Caller utterance transcribed: %s", clean_text)
            await self._respond(clean_text)
        except Exception as exc:
            logger.exception("Error processing caller utterance: %s", exc)
        finally:
            self.is_processing = False

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

        # If customer said yes or requested link, immediately trigger Razorpay payment link delivery
        norm = transcript.lower().strip()
        affirmative_words = (
            "yes", "haan", "han", "ji haan", "sahi hai", "theek hai", "accha",
            "hmm", "ok", "okay", "sure", "bhej", "send", "link", "kardo", "kar do",
            "kar dunga", "kar dungi", "abhi", "pay", "payment", "हाँ", "सही है", "ठीक है", "भेज", "लिंक"
        )
        if any(w in norm for w in affirmative_words) and self.intervention_id:
            try:
                payment_url = await asyncio.to_thread(self.voice_service.ensure_payment_link_sent, self.intervention_id)
                if payment_url:
                    logger.info("Payment link delivered via Razorpay / messaging for intervention %s: %s", self.intervention_id, payment_url)
            except Exception as exc:
                logger.warning("Failed triggering payment link on affirmative turn: %s", exc)

        if response_text:
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

        if response_text and ("dhanyawaad" in response_text.lower() or "payment link ready" in response_text.lower()):
            should_end = True

        logger.info("Agent reply: %s (close_after_playback=%s)", response_text, should_end)
        self.close_after_playback = should_end

        try:
            audio_wav = await asyncio.to_thread(self.speech_provider.synthesize, response_text, sample_rate=self._SAMPLE_RATE)
            await self._send_audio(audio_wav)
        except Exception as exc:
            logger.exception("Failed to synthesize or send agent reply: %s", exc)

    async def _send_audio(self, audio_wav: bytes) -> None:
        pcm = self._pcm_from_wav(audio_wav)
        if not pcm or not self.stream_id:
            return

        self.is_playing = True
        duration_seconds = len(pcm) / (self._SAMPLE_RATE * 2)
        logger.info("Sending TTS audio: stream_id=%s bytes=%d duration=%.2fs", self.stream_id, len(pcm), duration_seconds)

        # 20ms chunks (640 bytes for 16 kHz 16-bit mono)
        chunk_size = 640
        initial_burst_chunks = 20
        chunk_index = 0

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
            except Exception as exc:
                logger.warning("Failed sending playAudio frame: %s", exc)
                self.is_playing = False
                return

            chunk_index += 1
            # Flow subsequent chunks at steady paced rate (~1.3x real-time)
            # This fills Vobiz's buffer without overwhelming the WebSocket connection
            if chunk_index > initial_burst_chunks:
                await asyncio.sleep(0.015)

        # Send checkpoint so Vobiz reports playedStream once all audio completes
        try:
            await self.websocket.send_json({
                "event": "checkpoint",
                "streamId": self.stream_id,
                "name": f"tts-{uuid.uuid4().hex[:8]}",
            })
        except Exception:
            pass

        # Schedule safety fallback to reset is_playing in case playedStream event is delayed or missed
        self._spawn(self._safety_reset_playback(duration_seconds + 0.8))

    async def _safety_reset_playback(self, delay: float) -> None:
        await asyncio.sleep(delay)
        if self.is_playing:
            logger.info("Playback safety timer expired (%.2fs), resetting is_playing", delay)
            self.is_playing = False
        if self.close_after_playback:
            logger.info("Ending call after resolution playback safety timer (%.2fs)", delay)
            await asyncio.sleep(0.5)
            if self.intervention_id:
                try:
                    await asyncio.to_thread(self.voice_service.vobiz_call_completed, self.intervention_id, reason="safety_timer_resolution_complete")
                except Exception as exc:
                    logger.warning("Failed to mark call complete on safety timer: %s", exc)
            try:
                await self.websocket.close()
            except Exception:
                pass

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

    def _spawn(self, coroutine) -> asyncio.Task:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _cleanup(self) -> None:
        for task in list(self._tasks):
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # As a safety net, ensure the call is transitioned out of active states if stream closed
        if self.intervention_id:
            try:
                await asyncio.to_thread(self.voice_service.vobiz_call_completed, self.intervention_id, reason="session_cleanup")
            except Exception:
                pass

    async def _close_with_error(self) -> None:
        try:
            await self.websocket.close(code=1011, reason="voice stream failure")
        except Exception:
            pass
