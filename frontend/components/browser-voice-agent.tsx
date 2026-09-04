"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { PipecatClient } from "@pipecat-ai/client-js";
import { ProtobufFrameSerializer, WebSocketTransport } from "@pipecat-ai/websocket-transport";
import { ArrowRightIcon, CheckIcon, MicIcon, MicOffIcon, ShieldIcon } from "./icons";
import { api } from "../lib/api";
import { formatFailureReason, formatPaise } from "../lib/formatters";

type VoiceStatus = "idle" | "connecting" | "listening" | "speaking" | "muted" | "error";
type Speaker = "agent" | "customer" | "operator";

type TranscriptLine = {
  id: number;
  speaker: Speaker;
  text: string;
};

function readableError(error: unknown): string {
  if (typeof error === "string" && error.trim()) return error;
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "object" && error !== null) {
    const candidate = error as { message?: unknown; data?: { message?: unknown } };
    if (typeof candidate.message === "string" && candidate.message.trim()) return candidate.message;
    if (typeof candidate.data?.message === "string" && candidate.data.message.trim()) return candidate.data.message;
  }
  return "The voice session could not start. Check Sarvam credentials and browser microphone access.";
}

function statusLabel(status: VoiceStatus) {
  if (status === "connecting") return "Connecting";
  if (status === "speaking") return "Agent speaking";
  if (status === "muted") return "Microphone muted";
  if (status === "error") return "Needs attention";
  if (status === "listening") return "Listening";
  return "Ready for demo";
}

export function BrowserVoiceAgent({
  interventionId,
  amountPaise,
  failureReason,
  paymentMethod,
}: {
  interventionId: string;
  amountPaise: number;
  failureReason: string;
  paymentMethod: string;
}) {
  const clientRef = useRef<PipecatClient | null>(null);
  const nextLineId = useRef(1);
  const mutedRef = useRef(false);
  const sessionErrorRef = useRef(false);
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [textInput, setTextInput] = useState("");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);

  const addLine = (speaker: Speaker, text: string) => {
    const cleanText = text.trim();
    if (!cleanText) return;
    setTranscript((current) => [...current, { id: nextLineId.current++, speaker, text: cleanText }]);
  };

  const stop = async () => {
    const client = clientRef.current;
    clientRef.current = null;
    mutedRef.current = false;
    sessionErrorRef.current = false;
    setMuted(false);
    if (client) await client.disconnect();
    setStatus("idle");
  };

  const start = async () => {
    if (clientRef.current) return;
    setStatus("connecting");
    setError(null);
    sessionErrorRef.current = false;
    try {
      const client = new PipecatClient({
        transport: new WebSocketTransport({
          serializer: new ProtobufFrameSerializer(),
          recorderSampleRate: 16000,
          playerSampleRate: 16000,
        }),
        enableMic: true,
        enableCam: false,
        callbacks: {
          onConnected: () => setStatus("listening"),
          onDisconnected: () => {
            clientRef.current = null;
            mutedRef.current = false;
            setMuted(false);
            if (!sessionErrorRef.current) setStatus("idle");
          },
          onBotReady: () => setStatus("listening"),
          onBotStartedSpeaking: () => setStatus("speaking"),
          onBotStoppedSpeaking: () => setStatus(mutedRef.current ? "muted" : "listening"),
          onUserStartedSpeaking: () => setStatus("listening"),
          onUserTranscript: (data) => {
            if (data.final) addLine("customer", data.text);
          },
          onBotOutput: (data) => {
            if (data.spoken) addLine("agent", data.text);
          },
          onError: (message) => {
            sessionErrorRef.current = true;
            const failedClient = clientRef.current;
            clientRef.current = null;
            if (failedClient) void failedClient.disconnect();
            const nextError = readableError(message);
            setError(nextError);
            setStatus("error");
          },
          onDeviceError: (deviceError) => {
            sessionErrorRef.current = true;
            const failedClient = clientRef.current;
            clientRef.current = null;
            if (failedClient) void failedClient.disconnect();
            setError(readableError(deviceError));
            setStatus("error");
          },
        },
      });
      clientRef.current = client;
      await client.connect({ wsUrl: api.pipecatVoiceUrl(interventionId) });
    } catch (startError) {
      clientRef.current = null;
      sessionErrorRef.current = true;
      setError(readableError(startError));
      setStatus("error");
    }
  };

  const toggleMute = () => {
    const client = clientRef.current;
    if (!client || (status !== "listening" && status !== "muted")) return;
    const nextMuted = !muted;
    client.enableMic(!nextMuted);
    mutedRef.current = nextMuted;
    setMuted(nextMuted);
    setStatus(nextMuted ? "muted" : "listening");
  };

  const sendText = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = textInput.trim();
    const client = clientRef.current;
    if (!text || !client) return;
    addLine("operator", text);
    setTextInput("");
    try {
      await client.sendText(text);
    } catch (sendError) {
      setError(readableError(sendError));
      setStatus("error");
    }
  };

  useEffect(() => () => {
    const client = clientRef.current;
    clientRef.current = null;
    if (client) void client.disconnect();
  }, []);

  const active = Boolean(clientRef.current);
  return <section className="voice-agent-demo" aria-labelledby="browser-voice-agent-title">
    <div className="voice-agent-head">
      <div>
        <span className="section-overline">LIVE BROWSER DEMO</span>
        <h2 id="browser-voice-agent-title">Talk through the abandoned payment</h2>
        <p>Pipecat streams your voice to Sarvam and plays the agent response here. The demo is read-only.</p>
      </div>
      <span className={`voice-agent-status ${status}`}><span className="voice-agent-status-dot" />{statusLabel(status)}</span>
    </div>

    <div className="voice-agent-case" aria-label="Payment context">
      <div><span>Amount at risk</span><strong>{formatPaise(amountPaise)}</strong></div>
      <div><span>Failure reason</span><strong>{formatFailureReason(failureReason)}</strong></div>
      <div><span>Payment method</span><strong>{paymentMethod}</strong></div>
    </div>

    <div className="voice-agent-body">
      <div className="voice-agent-conversation">
        <div className="voice-agent-section-head"><div><span className="section-overline">CONVERSATION</span><strong>Live transcript</strong></div><small>Final speech is shown as it is recognized</small></div>
        <div className="voice-agent-transcript" role="log" aria-live="polite">
          {transcript.length === 0 && <div className="voice-agent-empty"><MicIcon size={18} /><span>Start the session and say, “payment link bhej do” or ask why it failed.</span></div>}
          {transcript.map((line) => <div className={`voice-agent-line ${line.speaker}`} key={line.id}><span>{line.speaker === "agent" ? "AGENT" : line.speaker === "customer" ? "YOU" : "TEXT"}</span><p>{line.text}</p></div>)}
        </div>
        {error && <div className="voice-agent-error" role="alert"><span><strong>Voice session unavailable</strong>{error}</span><button className="button button-secondary" type="button" onClick={start}>Try again<ArrowRightIcon size={14} /></button></div>}
        <div className="voice-agent-controls">
          {!active ? <button className="button button-primary voice-agent-start" type="button" onClick={start}><MicIcon size={16} />Start voice demo<ArrowRightIcon size={14} /></button> : <>
            <button className={`voice-agent-mic ${muted ? "muted" : ""}`} type="button" onClick={toggleMute} aria-label={muted ? "Unmute microphone" : "Mute microphone"}>{muted ? <MicOffIcon size={19} /> : <MicIcon size={19} />}<span>{muted ? "Unmute" : "Mute"}</span></button>
            <button className="button button-secondary" type="button" onClick={() => void stop()}>End session</button>
          </>}
        </div>
        <form className="voice-agent-text-form" onSubmit={sendText}><label htmlFor="voice-agent-text">Mic unavailable? Send a text turn</label><div><input id="voice-agent-text" value={textInput} onChange={(event) => setTextInput(event.target.value)} placeholder="e.g. link bhej do" disabled={!active} /><button className="square-control" type="submit" disabled={!active || !textInput.trim()} aria-label="Send text turn"><ArrowRightIcon size={15} /></button></div></form>
      </div>

      <aside className="voice-agent-guardrail"><div className="voice-agent-guardrail-head"><ShieldIcon size={17} /><span>Demo boundary</span></div><h3>Conversation only</h3><p>The agent can explain the failure and guide the next step. It cannot send a live payment link, collect credentials, or mark recovery complete.</p><div className="voice-agent-guardrail-list"><span><CheckIcon size={13} />Sarvam STT + TTS</span><span><CheckIcon size={13} />Hinglish responses</span><span><CheckIcon size={13} />No provider mutation</span></div></aside>
    </div>
  </section>;
}
