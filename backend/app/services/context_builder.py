from __future__ import annotations

from backend.chimera_simulator.context import build_observable_context
from backend.chimera_simulator.models import (
    ACTIONS,
    CONTACT_ACTIONS,
    ContactWindow,
    PaymentFailureEvent,
    SyntheticCustomer,
)


def build_event(case, simulator_config) -> PaymentFailureEvent:
    """Build only decision-time, synthetic observable context for an application case."""

    customer = SyntheticCustomer(
        customer_id=case.customer_id,
        synthetic_name=f"Synthetic Customer {case.customer_id}",
        synthetic_phone="+91-90000-00000",
        synthetic_email=f"{case.customer_id.lower()}@example.test",
        language_preference="english",
        communication_preference="allowed",
        consent_status="synthetic_demo_consent",
        subscription_state="active",
    )
    context = build_observable_context(
        customer=customer,
        historical_payments=(),
        prior_contacts=(),
        decision_timestamp=case.decision_timestamp,
        incident_flag=case.incident_flag,
        observation_window_days=simulator_config.observation_window_days,
    )
    defaults = simulator_config.raw["policy_defaults"]
    return PaymentFailureEvent(
        event_id=case.external_event_id,
        payment_id=case.payment_id,
        customer=customer,
        context=context,
        amount_paise=case.amount_paise,
        currency=case.currency,
        payment_method=case.payment_method,
        failure_reason=case.failure_reason,
        source_timestamp=case.decision_timestamp,
        decision_timestamp=case.decision_timestamp,
        available_actions=ACTIONS,
        contact_window=ContactWindow(
            start_local=defaults["contact_window_start"],
            end_local=defaults["contact_window_end"],
            timezone=defaults["contact_window_timezone"],
            contact_actions=tuple(defaults["contact_actions"]),
        ),
        action_is_outbound={**{action: action in CONTACT_ACTIONS for action in ACTIONS}, "HUMAN_OUTREACH": True},
    )
