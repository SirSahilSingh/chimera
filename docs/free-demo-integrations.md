# Free/trial recovery integrations

CHIMERA keeps the decision engine and recovery accounting provider-neutral. The
following optional adapters connect the existing persisted interventions to
free or trial services for a buildathon demonstration:

- Payment-link delivery uses Razorpay-native SMS/email notification when a
  customer contact is present. This keeps the payment-link provider and its
  customer notification in one boundary; no WhatsApp template or Sandbox is
  involved in the primary recovery path.
- WhatsApp remains an optional Twilio Sandbox integration. The recipient must
  join the Sandbox and be verified; proactive messages use a Twilio-approved
  template.
- Voice uses Twilio only as the phone carrier. Sarvam is the India-first speech
  layer: Saaras v3 transcribes code-mixed Hindi/English recordings and Bulbul
  v3 speaks the next response. Trial calls can be placed only to verified
  destinations and are subject to Twilio's trial limits. The call uses CHIMERA
  TwiML endpoints and the existing controlled intent classifier; no LLM key is
  required.
- Escalation uses the free Telegram Bot API as an optional operator
  notification. The internal CHIMERA escalation queue remains the source of
  truth when Telegram is disabled or unavailable.

## Setup order

1. Run `alembic upgrade head` against the deployment database so
   `recovery_cases.customer_phone` exists.
2. Configure Razorpay webhooks. CHIMERA captures `payment.entity.contact` from
   a webhook and prefers that persisted number for customer routing.
3. For payment-link delivery, no messaging provider is required: configure
   Razorpay with the customer phone or email and CHIMERA requests native
   notification delivery as part of link creation. Twilio WhatsApp can still
   be configured separately with `MESSAGING_PROVIDER=twilio` and
   `MESSAGING_CHANNEL=whatsapp`; it is not invoked for Razorpay links.
4. Configure Twilio with `VOICE_PUBLIC_BASE_URL` set to the public backend
   origin, set `VOICE_PROVIDER=twilio` and `VOICE_MODE=TEST` for the trial
   demo. Add `SARVAM_API_KEY`, `SARVAM_ENABLED=true`,
   `SARVAM_STT_MODEL=saaras:v3`, `SARVAM_STT_MODE=codemix`, and
   `SARVAM_TTS_MODEL=bulbul:v3`. Twilio's status and call-control callbacks
   must reach the `/voice/twilio` endpoints exposed by the API. Use the
   explicit live-execution switch only when changing the mode to `LIVE`.
5. Create a Telegram bot with BotFather, obtain the chat ID, and set
   `ESCALATION_PROVIDER=telegram`. Notification failure does not remove the
   escalation from the internal queue.

Credentials are never stored in CHIMERA records or returned to the frontend.

## Sarvam call loop

1. Twilio requests the first TwiML response from CHIMERA.
2. CHIMERA generates the prompt with Sarvam Bulbul and gives Twilio a short-lived WAV URL.
3. Twilio records the customer's answer and posts the recording URL back to CHIMERA.
4. CHIMERA fetches the recording, sends it to Sarvam Saaras with `codemix`, and classifies the transcript with the controlled voice policy.
5. CHIMERA records the intent, creates a Razorpay link when allowed, and speaks the next response with Sarvam Bulbul.

Prompts use native Hindi script mixed with English payment terms because Sarvam's TTS guidance recommends native Indic script over Romanized Indic text.
