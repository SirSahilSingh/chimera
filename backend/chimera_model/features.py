"""Explicit observable-only feature schema for recovery modeling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from backend.chimera_simulator.models import ACTIONS, PaymentFailureEvent


FEATURE_SCHEMA_VERSION = "features_v1.0.0"


class FeatureSchemaError(ValueError):
    """Raised when an event or action cannot be represented by the schema."""


class ForbiddenFeatureError(FeatureSchemaError):
    """Raised when a hidden or future-only field is presented to the builder."""


class TemporalLeakageError(FeatureSchemaError):
    """Raised when an observable record is newer than the decision timestamp."""


FORBIDDEN_FIELD_NAMES = (
    "hidden_state",
    "customer_segment",
    "environment_state",
    "natural_recovery_probability",
    "action_responsiveness",
    "action_outcomes",
    "recovery_probability",
    "recovered",
    "recovery_timestamp",
    "promise_to_pay_date",
    "verification_timestamp",
    "outcome",
    "future_outcome",
)


def _feature_names() -> tuple[str, ...]:
    names = [
        "amount_paise_scaled_1m",
        "successful_payment_ratio",
        "historic_recovery_rate",
        "contacts_last_7_days",
        "hour_sin",
        "hour_cos",
        "incident_flag",
    ]
    names.extend(f"day_of_week_{index}" for index in range(7))
    names.extend(f"payment_method_{value}" for value in ("card", "upi", "netbanking"))
    names.extend(
        f"failure_reason_{value}"
        for value in (
            "issuer_decline",
            "expired_method",
            "technical_degradation",
            "insufficient_funds",
            "abandonment",
            "other",
        )
    )
    names.extend(f"language_{value}" for value in ("english", "hinglish"))
    names.append("communication_preference_allowed")
    names.append("subscription_state_active")
    names.extend(f"last_channel_{value}" for value in ("none", "message", "voice", "payment_link"))
    names.extend(f"prior_response_{value}" for value in ("none", "ignored", "read", "willing_to_pay"))
    names.extend(("candidate_action_is_outbound", "candidate_action_contact_window_eligible"))
    names.extend(f"candidate_action_{action}" for action in ACTIONS)
    return tuple(names)


@dataclass(frozen=True)
class FeatureSchema:
    version: str
    feature_names: tuple[str, ...]
    allowed_source_fields: tuple[str, ...]
    forbidden_source_fields: tuple[str, ...]

    @classmethod
    def current(cls) -> "FeatureSchema":
        return cls(
            version=FEATURE_SCHEMA_VERSION,
            feature_names=_feature_names(),
            allowed_source_fields=(
                "amount_paise",
                "currency",
                "payment_method",
                "failure_reason",
                "source_timestamp",
                "decision_timestamp",
                "context.successful_payment_ratio",
                "context.historic_recovery_rate",
                "context.contacts_last_7_days",
                "context.last_channel",
                "context.prior_response",
                "context.hour",
                "context.day_of_week",
                "context.incident_flag",
                "context.language_preference",
                "context.communication_preference",
                "context.subscription_state",
                "contact_window",
                "action_is_outbound",
                "candidate_action",
            ),
            forbidden_source_fields=FORBIDDEN_FIELD_NAMES,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "feature_names": list(self.feature_names),
            "allowed_source_fields": list(self.allowed_source_fields),
            "forbidden_source_fields": list(self.forbidden_source_fields),
        }


def _clock_minutes(value: str) -> int:
    try:
        hour_text, minute_text = value.split(":")
        hour, minute = int(hour_text), int(minute_text)
    except (AttributeError, ValueError) as exc:
        raise FeatureSchemaError(f"invalid contact-window time: {value!r}") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise FeatureSchemaError(f"invalid contact-window time: {value!r}")
    return hour * 60 + minute


def _contact_window_eligible(event: PaymentFailureEvent, action: str) -> bool:
    if not event.action_is_outbound.get(action, False):
        return True
    start = _clock_minutes(event.contact_window.start_local)
    end = _clock_minutes(event.contact_window.end_local)
    current = event.context.hour * 60
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _ensure_allowed_boundary(event: PaymentFailureEvent) -> None:
    if not isinstance(event, PaymentFailureEvent):
        raise FeatureSchemaError("feature builder accepts only PaymentFailureEvent, not simulator truth records")

    for object_name, object_value in (
        ("event", event),
        ("context", event.context),
        ("customer", event.customer),
        ("contact_window", event.contact_window),
    ):
        present = set(vars(object_value))
        forbidden = present.intersection(FORBIDDEN_FIELD_NAMES)
        if forbidden:
            raise ForbiddenFeatureError(f"forbidden fields on {object_name}: {sorted(forbidden)}")

    decision_timestamp = event.decision_timestamp
    if event.source_timestamp > decision_timestamp:
        raise TemporalLeakageError("event source_timestamp is after decision_timestamp")
    if event.context.source_timestamp > decision_timestamp:
        raise TemporalLeakageError("context source_timestamp is after decision_timestamp")
    for payment in event.context.historical_payments:
        if payment.source_timestamp > decision_timestamp:
            raise TemporalLeakageError(f"future historical payment entered features: {payment.payment_id}")
    for contact in event.context.prior_contacts:
        if contact.source_timestamp > decision_timestamp:
            raise TemporalLeakageError(f"future contact entered features: {contact.contact_id}")


class ObservableFeatureBuilder:
    """Build the fixed feature vector from decision-time observables only."""

    def __init__(self, schema: FeatureSchema | None = None) -> None:
        self.schema = schema or FeatureSchema.current()

    def validate_event(self, event: PaymentFailureEvent) -> None:
        _ensure_allowed_boundary(event)

    def build_mapping(self, event: PaymentFailureEvent, candidate_action: str) -> dict[str, float]:
        self.validate_event(event)
        if candidate_action not in ACTIONS:
            raise FeatureSchemaError(f"unknown candidate action: {candidate_action}")
        if candidate_action not in event.available_actions:
            raise FeatureSchemaError(f"candidate action is unavailable for event: {candidate_action}")

        context = event.context
        hour_radians = 2.0 * np.pi * context.hour / 24.0
        values: dict[str, float] = {
            "amount_paise_scaled_1m": event.amount_paise / 1_000_000.0,
            "successful_payment_ratio": float(context.successful_payment_ratio),
            "historic_recovery_rate": float(context.historic_recovery_rate),
            "contacts_last_7_days": float(context.contacts_last_7_days),
            "hour_sin": float(np.sin(hour_radians)),
            "hour_cos": float(np.cos(hour_radians)),
            "incident_flag": float(context.incident_flag),
        }
        values.update({f"day_of_week_{index}": float(context.day_of_week == index) for index in range(7)})
        values.update(
            {f"payment_method_{value}": float(event.payment_method == value) for value in ("card", "upi", "netbanking")}
        )
        values.update(
            {
                f"failure_reason_{value}": float(event.failure_reason == value)
                for value in (
                    "issuer_decline",
                    "expired_method",
                    "technical_degradation",
                    "insufficient_funds",
                    "abandonment",
                    "other",
                )
            }
        )
        values.update({f"language_{value}": float(context.language_preference == value) for value in ("english", "hinglish")})
        values["communication_preference_allowed"] = float(context.communication_preference == "allowed")
        values["subscription_state_active"] = float(context.subscription_state == "active")
        values.update(
            {
                f"last_channel_{value}": float((context.last_channel or "none") == value)
                for value in ("none", "message", "voice", "payment_link")
            }
        )
        values.update(
            {
                f"prior_response_{value}": float((context.prior_response or "none") == value)
                for value in ("none", "ignored", "read", "willing_to_pay")
            }
        )
        values["candidate_action_is_outbound"] = float(event.action_is_outbound.get(candidate_action, False))
        values["candidate_action_contact_window_eligible"] = float(
            _contact_window_eligible(event, candidate_action)
        )
        values.update({f"candidate_action_{action}": float(candidate_action == action) for action in ACTIONS})

        missing = set(self.schema.feature_names).difference(values)
        extra = set(values).difference(self.schema.feature_names)
        if missing or extra:
            raise FeatureSchemaError(f"feature schema mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
        return {name: values[name] for name in self.schema.feature_names}

    def build_vector(self, event: PaymentFailureEvent, candidate_action: str) -> np.ndarray:
        mapping = self.build_mapping(event, candidate_action)
        return np.asarray([mapping[name] for name in self.schema.feature_names], dtype=np.float64)


def build_feature_builder(schema: FeatureSchema | None = None) -> ObservableFeatureBuilder:
    return ObservableFeatureBuilder(schema)
