# Provider integration and demo boundary

Gate 14 keeps provider execution behind the existing payment, messaging, voice,
and retry services. The decision and intervention records remain authoritative;
providers cannot select or replace an action.

## Modes

`LOCAL` is deterministic and safe for demos. `MOCK` is simulated provider
execution. `TEST` is reserved for provider sandbox credentials. `LIVE` is the
only mode that may make an external call. Each persisted provider record stores
its provider, mode, reference, status, and idempotency key where applicable.

Use `POST /api/v1/demo/run` with one of `payment_recovery`, `technical_retry`,
`voice_recovery`, or `escalation`. The endpoint builds a synthetic case, runs
the stored decision, queues the stored intervention, and invokes the existing
service boundary. Demo runs require `provider_mode: LOCAL`; they never call a
third-party provider. The response includes a journey URL for inspection.

## External configuration

Provider credentials are read from environment variables and are never placed
in API responses, provider payload records, or failure messages. Razorpay uses
`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, and
`RAZORPAY_MODE`. Twilio and the provider-neutral voice adapter use the names in
`.env.example`. Missing credentials produce a controlled failure and leave the
application safe to run in local mode.

## Webhook safety

Signatures are verified before parsing. Provider event IDs are idempotent;
payload hashes and sanitized status metadata are persisted. Duplicate events
return the stored record, while stale events cannot move a terminal lifecycle
backward. Recovery is recorded only by the payment service after a validated
provider confirmation, never by a redirect or frontend callback.
