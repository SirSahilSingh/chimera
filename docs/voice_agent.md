# Gate 8 Voice Recovery Agent

Gate 8 adds a controlled voice execution layer for interventions whose stored
action is exactly `VOICE_RECOVERY`. It does not select actions, rerun the
decision engine, expose probabilities, or mark payment recovery from speech.

## Architecture

`VoiceService` consumes the persisted Gate 7 `Intervention`. If the
intervention is `READY`, it invokes the existing Gate 7 execution boundary,
which validates the stored action and moves the intervention to
`AWAITING_OUTCOME`. A separate `VoiceCall` then follows:

```text
CALL_QUEUED → CALL_INITIATED → RINGING → CONNECTED → CONVERSATION
                                                    ↓
                                      AWAITING_RESOLUTION → terminal
```

`VoiceTurn` and `VoiceEvent` rows are append-only. The call lifecycle is
validated independently from the intervention lifecycle. Positive intents
(`PAY_NOW`, payment-link request, retry later, or already paid) are recorded as
conversation outcomes only; payment recovery still requires a validated
payment outcome. A decline records `NOT_RECOVERED` through the existing Gate 7
outcome service.

## Context and safety

`VoiceContext` is an `extra="forbid"` allowlist containing only persisted
observable payment fields, stable references, the selected `VOICE_RECOVERY`
action, and configured conversational options. Hidden simulator state,
customer segments, environment state, probabilities, model internals, future
outcomes, credentials, and arbitrary action requests are rejected or never
constructed. Agent text is checked for unapproved numeric claims.

## Providers

Local mode is the default and needs no credentials. Set `VOICE_PROVIDER=live`,
`VOICE_ENABLED=true`, `VOICE_BASE_URL`, `VOICE_API_KEY`, `VOICE_AGENT_ID`, and
`VOICE_PHONE_NUMBER` to use the provider-neutral HTTP adapter. The adapter
expects `POST {VOICE_BASE_URL}/calls` and a response containing `call_id`,
`id`, or `reference`; vendor-specific translation belongs outside the
intervention lifecycle. Secrets are used only in memory and are not persisted
or returned.

## Demo

Run the local deterministic demo with:

```powershell
& "C:\Users\sahil\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" backend/scripts/run_voice_demo.py
```

The demo covers agreement, payment-link request, and decline/no-answer paths.
The same scenario and intervention/provider idempotency key reproduce the same
provider reference, payment link, intent, and transcript hash.

Razorpay and payment-gateway integration are not included in Gate 8.
