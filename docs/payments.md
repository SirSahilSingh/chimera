# Gate 9 Payment Boundary

The payment boundary is a provider-neutral adapter around the stored Gate 5 `RecoveryCase`, `Decision`, and Gate 7 `Intervention`. It does not recompute a decision. A link can be created only for a stored `PAYMENT_LINK` intervention or after Gate 8 has validated `SEND_PAYMENT_LINK` during a `VOICE_RECOVERY` call.

Provider transport retries are limited to one retry for timeout/network failures. The request uses the same deterministic reference and service idempotency key, so an internal retry cannot create a second persisted link. Provider failures are reduced to controlled safe codes.

## Local demo

Local mode is the default and never contacts Razorpay. Create a queued intervention, create its payment link, then use `POST /api/v1/payments/{payment_id}/demo/complete` with one of `payment_success`, `payment_pending`, `payment_expired`, `payment_failed`, `duplicate_webhook`, `invalid_webhook`, or `out_of_order_event`. Local URLs use `https://demo.chimera.local/` and are not payment claims. `python backend/scripts/run_payment_demo.py` prints three end-to-end traces.

## Razorpay configuration

Set `PAYMENT_PROVIDER=razorpay`, `PAYMENT_ENABLED=true`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, and optionally `PAYMENT_TIMEOUT_SECONDS`. Razorpay test keys must be used for development. The adapter calls the Payment Links API using Basic authentication, stores only provider references and sanitized hashes, and verifies the raw webhook body with HMAC-SHA256 and the configured webhook secret. Configure Razorpay to send payment-link events to `/api/v1/payments/webhook/razorpay` and pass the signature in `X-Razorpay-Signature`. Standard Payment Links remain in the `created` state while awaiting payment; a failed checkout is handled from the `payment.failed` event and correlated using its `order_id` or reference association.

## Recovery boundary

Creating or opening a link is not recovery. Only a validated provider success event with matching integer paise amount and INR currency calls the existing intervention lifecycle with `RECOVERED`. Duplicate provider event IDs are idempotent; stale events cannot revert `PAID`. Failed, expired, and pending observations are persisted as events and never count as recovery. Secrets and raw provider errors are excluded from responses and audit payloads.
# Initial checkout architecture

CHIMERA separates the initial merchant checkout from recovery payment links.

- `POST /api/v1/payments/orders` creates the initial Razorpay Order. The response contains a publishable `checkout_key_id` and `provider_order_id`; the frontend opens Razorpay Checkout with those values.
- Razorpay sends signed `payment.failed` or `payment.captured` webhooks to `/api/v1/payments/webhook/razorpay`.
- A failed initial order is persisted first, then CHIMERA creates the recovery case, runs the deterministic decision engine, and routes the selected intervention.
- Payment Links remain a recovery action. Their paid/expired/failed outcomes continue through the existing `PaymentLink` lifecycle.
- The webhook handler is idempotent by provider event ID. The order is correlated by `order_id`, so the initial failure does not depend on a hosted Payment Link exposing a link ID.

The initial checkout API never returns a provider secret. It stores customer contact data on the order so the recovery case can inherit it when a failure event arrives.
