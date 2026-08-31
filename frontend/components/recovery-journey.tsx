"use client";

import Link from "next/link";
import { ArrowRightIcon, CheckIcon, ClockIcon, ExternalIcon, ShieldIcon } from "./icons";
import { StatusBadge } from "./shell";
import { formatAction, formatDate, formatPaise } from "../lib/formatters";
import type { JourneyEvent, JourneyPayment, JourneyVoiceCall, RecoveryJourney } from "../lib/types";

function eventLabel(event: JourneyEvent) {
  return event.event_type.replaceAll("_", " ").replaceAll(".", " · ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function modeLabel(mode: string | null | undefined) {
  return mode ? mode : "Not recorded";
}

export function PersistedJourneyTimeline({ journey }: { journey: RecoveryJourney }) {
  return <section className="journey-panel" aria-label="Persisted recovery audit trail">
    <div className="panel-heading"><div><span className="section-overline">Audit trail</span><h2>The complete recovery story</h2></div><span className="panel-note">Persisted events · chronological</span></div>
    {journey.audit_trail.length ? <div className="journey-timeline">{journey.audit_trail.map((event, index) => <div className="journey-event" key={`${event.id}-${index}`}><div className="journey-spine"><span className={`journey-marker ${index === journey.audit_trail.length - 1 ? "latest" : ""}`} />{index < journey.audit_trail.length - 1 && <i />}</div><div className="journey-event-body"><div className="journey-event-head"><strong>{eventLabel(event)}</strong><time>{event.timestamp ? formatDate(event.timestamp) : "Timestamp unavailable"}</time></div><p>{event.source}{event.provider_mode ? ` · ${modeLabel(event.provider_mode)}` : ""}</p></div></div>)}</div> : <div className="inline-empty"><ExternalIcon size={16} /><span>No persisted audit events are available for this case.</span></div>}
  </section>;
}

export function ProviderJourney({ journey }: { journey: RecoveryJourney }) {
  const payments = journey.payments;
  const messages = journey.messages;
  const retries = journey.retries;
  const schedules = journey.scheduled_retries;
  const escalations = journey.escalations;
  const calls = journey.voice_calls;
  const hasOperations = payments.length || messages.length || retries.length || schedules.length || escalations.length || calls.length;
  if (!hasOperations) return null;
  return <section className="provider-journey" aria-label="Provider operations">
    <div className="panel-heading"><div><span className="section-overline">Intervention evidence</span><h2>What happened after the decision</h2></div><span className="panel-note">Provider records only</span></div>
    <div className="provider-grid">
      {payments.map((payment) => <PaymentOperation key={payment.id} payment={payment} />)}
      {calls.map((call) => <VoiceOperation key={call.id} call={call} />)}
      {messages.map((message) => <OperationRow key={message.id} title="Message delivery" provider={message.provider} mode={message.provider_mode} status={message.delivery_state} detail={message.failure_reason ?? message.provider_message_id ?? "Provider reference not returned"} />)}
      {schedules.map((schedule) => <OperationRow key={schedule.id} title="Retry scheduled" provider="Retry scheduler" mode={schedule.provider_mode} status={schedule.execution_status} detail={`Scheduled for ${formatDate(schedule.scheduled_at)}`} />)}
      {retries.map((retry) => <OperationRow key={retry.id} title={formatAction(retry.action)} provider={retry.provider} mode={retry.provider_mode} status={retry.status} detail={retry.provider_reference ?? "Outcome pending"} />)}
      {escalations.map((escalation) => <OperationRow key={escalation.id} title="Human escalation" provider="Escalation workflow" mode={escalation.provider_mode} status={escalation.status} detail={escalation.reason} />)}
    </div>
  </section>;
}

function OperationRow({ title, provider, mode, status, detail }: { title: string; provider: string; mode: string; status: string; detail: string }) {
  return <article className="provider-operation"><div className="provider-operation-icon"><ShieldIcon size={17} /></div><div className="provider-operation-copy"><div><strong>{title}</strong><StatusBadge status={status} /></div><p>{detail}</p><small>{provider} · <b>{modeLabel(mode)}</b></small></div></article>;
}

function PaymentOperation({ payment }: { payment: JourneyPayment }) {
  const paid = payment.status === "PAID";
  return <article className={`provider-operation payment-operation ${paid ? "paid" : ""}`}><div className="provider-operation-icon">{paid ? <CheckIcon size={17} /> : <ClockIcon size={17} />}</div><div className="provider-operation-copy"><div><strong>Payment link</strong><StatusBadge status={payment.status} /></div><p>{paid ? `${formatPaise(payment.amount_paise)} recovered after provider confirmation.` : "Link created; recovery remains pending until payment confirmation."}</p><small>{payment.provider} · <b>{modeLabel(payment.provider_mode)}</b></small><Link href={payment.short_url} target="_blank" className="operation-link">Open payment link <ArrowRightIcon size={13} /></Link></div></article>;
}

function VoiceOperation({ call }: { call: JourneyVoiceCall }) {
  const demo = ["LOCAL", "MOCK", "TEST"].includes(call.provider_mode);
  return <article className="provider-operation voice-operation"><div className="provider-operation-icon"><ExternalIcon size={17} /></div><div className="provider-operation-copy"><div><strong>Voice recovery</strong><StatusBadge status={call.status} /></div><p>{call.outcome_intent ? `Latest intent: ${call.outcome_intent.replaceAll("_", " ")}` : "Conversation state is persisted below."}</p><small>{demo ? "Demo Voice Agent" : "Live voice provider"} · {call.provider} · <b>{modeLabel(call.provider_mode)}</b></small>{call.turns.length ? <div className="conversation-log">{call.turns.map((turn) => <div className={`conversation-turn ${turn.speaker}`} key={turn.id}><span>{turn.speaker === "agent" ? "CHIMERA" : "CUSTOMER"}</span><p>{turn.text}</p></div>)}</div> : <div className="operation-empty">No persisted conversation turns yet.</div>}</div></article>;
}
