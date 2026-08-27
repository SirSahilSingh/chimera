# Provider Readiness

Gate 16 adds a read-only readiness layer at `/api/v1/providers`. It describes
configured provider capabilities without changing stored decisions or
interventions. `POST /api/v1/providers/{name}/verify` records an explicit
verification attempt; it never creates a payment link, call, SMS, retry, or
charge. `POST /api/v1/providers/{name}/test` requires `{"confirm": true}` and
is limited to `TEST`, `SANDBOX`, or explicitly enabled `LIVE` mode.

## Modes and statuses

- `LOCAL` / `MOCK`: deterministic or simulated execution; readiness is
  `MOCK_VERIFIED`, never live proof.
- `TEST`: provider test endpoint; a successful safe probe is `TEST_VERIFIED`.
- `SANDBOX`: provider sandbox; a successful safe probe is `SANDBOX_VERIFIED`.
- `LIVE`: real provider configuration; it remains `CONFIGURED` until an
  explicit safe probe succeeds while `CHIMERA_ALLOW_LIVE_EXECUTION=true`.
- `NOT_CONFIGURED`, `FAILED`, and `UNAVAILABLE` are reported honestly with
  controlled error categories only.

## Configuration and truth

Set provider credentials server-side using the existing `RAZORPAY_*`,
`TWILIO_*`, and `VOICE_*` variables. `CHIMERA_ALLOW_LIVE_EXECUTION` defaults
to `false`; credentials alone never enable live execution. No credential,
signature, authorization header, or raw provider response is returned or
persisted.

Razorpay verification performs a read-only payment-link listing probe. Twilio
verification performs a read-only account probe. The voice adapter performs a
provider-neutral `GET /health` probe. None creates a charge, payment link,
call, or SMS. Existing webhook boundaries remain signature-verified and
idempotent.

Gate 16 is implemented and locally/mock verified. No TEST, SANDBOX, or LIVE
external request was performed in this environment, so no external provider
is claimed as `TEST_VERIFIED`, `SANDBOX_VERIFIED`, or `LIVE_VERIFIED`.

