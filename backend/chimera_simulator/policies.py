"""Deterministic baseline policies for the Gate 2 Arena."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import PaymentFailureEvent


@dataclass(frozen=True)
class PolicySelection:
    selected_action: str
    reason: str


class DeterministicPolicy(Protocol):
    """Policy contract: implementations receive only a decision-facing event."""

    name: str

    def choose_action(self, event: PaymentFailureEvent) -> PolicySelection:
        ...


class NoInterventionPolicy:
    name = "NO_INTERVENTION"

    def choose_action(self, event: PaymentFailureEvent) -> PolicySelection:
        return PolicySelection("DO_NOTHING", "Always choose the no-intervention baseline.")


class RetryAllPolicy:
    """Retry immediately unless observable incident signals make that invalid."""

    name = "RETRY_ALL"

    def choose_action(self, event: PaymentFailureEvent) -> PolicySelection:
        technically_valid = not event.context.incident_flag and event.failure_reason != "technical_degradation"
        if technically_valid:
            return PolicySelection(
                "RETRY_NOW",
                "Retry immediately because no observable incident or technical-degradation signal is present.",
            )
        return PolicySelection(
            "RETRY_LATER",
            "Delay retry because an observable incident or technical-degradation signal is present.",
        )


class SimpleRuleBasedPolicy:
    """Small transparent rule set using only PaymentFailureEvent observables."""

    name = "SIMPLE_RULE_BASED"

    def choose_action(self, event: PaymentFailureEvent) -> PolicySelection:
        if event.context.incident_flag:
            return PolicySelection("RETRY_LATER", "Incident flag is true; wait for system conditions to improve.")
        if event.failure_reason == "expired_method":
            return PolicySelection("PAYMENT_LINK", "Expired payment method indicates a replacement payment path.")
        if event.failure_reason == "abandonment":
            return PolicySelection("SEND_MESSAGE", "Abandonment is handled with one low-cost outbound message.")
        if event.failure_reason in {"technical_degradation", "insufficient_funds"}:
            return PolicySelection("RETRY_LATER", "The observable failure reason favors delayed retry.")
        return PolicySelection("RETRY_NOW", "Default rule for remaining observable failure reasons.")


def primary_baseline_policies() -> tuple[DeterministicPolicy, ...]:
    return (NoInterventionPolicy(), RetryAllPolicy(), SimpleRuleBasedPolicy())
