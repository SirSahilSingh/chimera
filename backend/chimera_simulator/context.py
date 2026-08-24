"""Temporal context construction with an explicit decision-time cutoff."""

from __future__ import annotations

from datetime import datetime, timedelta

from .models import ContactEvent, HistoricalPayment, ObservableContext, SyntheticCustomer


def build_observable_context(
    customer: SyntheticCustomer,
    historical_payments: tuple[HistoricalPayment, ...] | list[HistoricalPayment],
    prior_contacts: tuple[ContactEvent, ...] | list[ContactEvent],
    decision_timestamp: datetime,
    incident_flag: bool,
    observation_window_days: int = 30,
) -> ObservableContext:
    """Build context using only records at or before the decision timestamp."""

    observation_start = decision_timestamp - timedelta(days=observation_window_days)
    observed_payments = tuple(
        sorted(
            (
                payment
                for payment in historical_payments
                if observation_start <= payment.source_timestamp <= decision_timestamp
            ),
            key=lambda payment: payment.source_timestamp,
        )
    )
    observed_contacts = tuple(
        sorted(
            (
                contact
                for contact in prior_contacts
                if observation_start <= contact.source_timestamp <= decision_timestamp
            ),
            key=lambda contact: contact.source_timestamp,
        )
    )
    successful_count = sum(payment.outcome == "succeeded" for payment in observed_payments)
    total_count = len(observed_payments)
    successful_payment_ratio = successful_count / total_count if total_count else 0.0
    contacts_start = decision_timestamp - timedelta(days=7)
    recent_contacts = tuple(
        contact for contact in observed_contacts if contacts_start <= contact.source_timestamp <= decision_timestamp
    )
    last_contact = observed_contacts[-1] if observed_contacts else None
    return ObservableContext(
        customer_id=customer.customer_id,
        synthetic_name=customer.synthetic_name,
        synthetic_phone=customer.synthetic_phone,
        synthetic_email=customer.synthetic_email,
        language_preference=customer.language_preference,
        communication_preference=customer.communication_preference,
        consent_status=customer.consent_status,
        subscription_state=customer.subscription_state,
        successful_payment_ratio=successful_payment_ratio,
        historic_recovery_rate=successful_payment_ratio,
        contacts_last_7_days=len(recent_contacts),
        last_channel=last_contact.channel if last_contact else None,
        prior_response=last_contact.response if last_contact else None,
        hour=decision_timestamp.hour,
        day_of_week=decision_timestamp.weekday(),
        incident_flag=incident_flag,
        source_timestamp=decision_timestamp,
        historical_payments=observed_payments,
        prior_contacts=observed_contacts,
    )
