# Gate 10 Messaging, Retry, and Recovery Orchestration

Gate 10 routes an already-persisted Gate 7 `Intervention`. It reads
`Intervention.action` and never calls the decision engine or changes stored
probabilities, values, costs, fatigue, constraints, or tie-breaking.

## Action boundaries

- `SEND_MESSAGE` uses `MessagingService` and versioned, deterministic templates.
  The local provider records a delivered synthetic message; the optional Twilio
  adapter is backend-only. An active Gate 9 payment link is reused, otherwise
  the Gate 9 boundary creates one for this message workflow.
- `RETRY_NOW` creates one idempotent retry attempt. `RETRY_LATER` creates one
  deterministic schedule for 24 hours after the stored decision timestamp and
  cannot execute before that time. Provider acceptance is not recovery.
- `ESCALATE` creates an operator queue record with append-only status events.
- `PAYMENT_LINK` and `VOICE_RECOVERY` continue through Gates 9 and 8.
- `DO_NOTHING` creates an explicit audit marker and calls no provider.

## Configuration

Local mode needs no credentials. Optional messaging configuration uses
`MESSAGING_PROVIDER`, `MESSAGING_ENABLED`, `TWILIO_ACCOUNT_SID`,
`TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_TO_NUMBER`, and
`MESSAGING_TIMEOUT_SECONDS`. `RETRY_PROVIDER=local` is the deterministic
default; `live` is an explicit unavailable boundary until a real retry gateway
is configured.

The Twilio webhook boundary validates `X-Twilio-Signature` using the configured
auth token, callback URL, and sorted form parameters. Local callbacks use the
explicit local HMAC path only.

## Demo

Run `python backend/scripts/run_orchestration_demo.py` for technical retry,
expired-method message, insufficient-funds retry-later, escalation, and
DO_NOTHING traces. All demo identities and provider results are synthetic.
