# Gate 11 Live Provider Demo

Gate 11 connects the existing authorized intervention to provider boundaries. The deterministic decision engine remains the only action selector; this gate does not recompute decisions.

## Modes and configuration

Every operation is labelled `LOCAL`, `MOCK`, `TEST`, or `LIVE` and the value is persisted on provider records/events. `LOCAL` uses deterministic in-process providers. `MOCK` is reserved for injected test doubles. `TEST` and `LIVE` require explicit provider configuration and are never implied by a local provider.

Server-side variables are listed in `.env.example`:

- Razorpay: `PAYMENT_PROVIDER=razorpay`, `PAYMENT_MODE=TEST` (or `LIVE`), `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`.
- Twilio-compatible messaging: `MESSAGING_PROVIDER=twilio`, `MESSAGING_MODE=TEST` (or `LIVE`), `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, and `TWILIO_TO_NUMBER`.
- Optional voice HTTP adapter: `VOICE_PROVIDER=live`, `VOICE_MODE=TEST` (or `LIVE`), `VOICE_ENABLED=true`, `VOICE_BASE_URL`, `VOICE_API_KEY`, `VOICE_AGENT_ID`, and `VOICE_PHONE_NUMBER`.

Credentials stay on the server. Provider adapters bound timeouts, verify webhook signatures, retain only sanitized payloads/hashes, and deduplicate provider event IDs.

## Demo workflow

Run the API locally with the repository runtime, then submit observable-only case data:

```powershell
& "C:\Users\sahil\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m backend.scripts.run_live_demo
```

The script calls `POST /api/v1/demo/recovery`, which creates the case, invokes the existing deterministic decision, authorizes the intervention, and routes the stored action. Inspect the result with `GET /api/v1/recovery-cases/{case_id}/journey`. A local link becomes `RECOVERED` only after a valid signed local payment event; message delivery, retry acceptance, and voice agreement remain non-payment outcomes.

For Razorpay, configure `/api/v1/payments/webhook/razorpay`; for Twilio use `/api/v1/messaging/webhook/twilio`. Use provider test credentials and a test customer only. If credentials are absent, report the run as `LOCAL`; never label it live.

Scenarios A–E are reproducible by submitting cases with the corresponding observable failure context and following the stored selected action. The journey endpoint exposes detection, diagnosis, intervention, provider records, outcomes, and a deterministic chronological audit stream.
