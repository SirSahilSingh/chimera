"""Public data contracts for observable simulator events and internal truth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

ACTIONS = (
    "RETRY_NOW",
    "RETRY_LATER",
    "PAYMENT_LINK",
    "SEND_MESSAGE",
    "VOICE_RECOVERY",
    "ESCALATE",
    "DO_NOTHING",
)
CONTACT_ACTIONS = ("SEND_MESSAGE", "VOICE_RECOVERY", "HUMAN_OUTREACH")
ROOT_CAUSES = (
    "issuer_decline",
    "expired_method",
    "technical_degradation",
    "insufficient_funds",
    "abandonment",
    "other",
)
SEGMENTS = (
    "NATURAL_PAYER",
    "TEMPORARY_LIQUIDITY",
    "EXPIRED_METHOD_TENDENCY",
    "LOW_ENGAGEMENT",
)
ENVIRONMENT_STATES = (
    "NORMAL",
    "GATEWAY_DEGRADATION",
    "ISSUER_NETWORK_DEGRADATION",
)
SPLITS = (
    "training",
    "validation",
    "holdout",
    "arena_development",
    "arena_final",
)


@dataclass(frozen=True)
class ContactWindow:
    start_local: str
    end_local: str
    timezone: str
    contact_actions: tuple[str, ...]


@dataclass(frozen=True)
class SyntheticCustomer:
    customer_id: str
    synthetic_name: str
    synthetic_phone: str
    synthetic_email: str
    language_preference: str
    communication_preference: str
    consent_status: str
    subscription_state: str


@dataclass(frozen=True)
class HistoricalPayment:
    payment_id: str
    source_timestamp: datetime
    amount_paise: int
    outcome: str
    provider_code: str


@dataclass(frozen=True)
class ContactEvent:
    contact_id: str
    source_timestamp: datetime
    channel: str
    response: str | None


@dataclass(frozen=True)
class ObservableContext:
    """Decision-facing context; hidden state and future outcomes are absent by type."""

    customer_id: str
    synthetic_name: str
    synthetic_phone: str
    synthetic_email: str
    language_preference: str
    communication_preference: str
    consent_status: str
    subscription_state: str
    successful_payment_ratio: float
    historic_recovery_rate: float
    contacts_last_7_days: int
    last_channel: str | None
    prior_response: str | None
    hour: int
    day_of_week: int
    incident_flag: bool
    source_timestamp: datetime
    historical_payments: tuple[HistoricalPayment, ...]
    prior_contacts: tuple[ContactEvent, ...]


@dataclass(frozen=True)
class PaymentFailureEvent:
    """The only event shape that future policy interfaces should receive."""

    event_id: str
    payment_id: str
    customer: SyntheticCustomer
    context: ObservableContext
    amount_paise: int
    currency: str
    payment_method: str
    failure_reason: str
    source_timestamp: datetime
    decision_timestamp: datetime
    available_actions: tuple[str, ...]
    contact_window: ContactWindow
    action_is_outbound: Mapping[str, bool]


@dataclass(frozen=True)
class HiddenState:
    """Simulator-only truth; never placed on PaymentFailureEvent or ObservableContext."""

    customer_id: str
    customer_segment: str
    environment_state: str
    natural_recovery_probability: float
    action_responsiveness: Mapping[str, float]


@dataclass(frozen=True)
class ActionOutcome:
    action: str
    recovery_probability: float
    recovered: bool
    status: str
    recovery_timestamp: datetime | None
    promise_to_pay_date: datetime | None
    verification_timestamp: datetime | None
    outreach_paused: bool
    action_cost_paise: int
    incentive_cost_paise: int
    fatigue_penalty_paise: int


@dataclass(frozen=True)
class SimulatorOutcome:
    event_id: str
    horizon_start: datetime
    horizon_end: datetime
    action_outcomes: tuple[ActionOutcome, ...]

    def for_action(self, action: str) -> ActionOutcome:
        for result in self.action_outcomes:
            if result.action == action:
                return result
        raise KeyError(action)


@dataclass(frozen=True)
class GeneratedCase:
    """Internal simulator record combining decision-facing event and evaluation truth."""

    event: PaymentFailureEvent
    hidden_state: HiddenState
    outcome: SimulatorOutcome
