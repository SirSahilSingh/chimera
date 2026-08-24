"""Deterministic synthetic simulator foundation for CHIMERA Gate 1."""

from .config import ConfigurationError, SimulatorConfig
from .arena import ArenaReport, ArenaRunner, InvalidPolicyActionError, PolicyDecisionRecord
from .models import (
    ACTIONS,
    CONTACT_ACTIONS,
    ENVIRONMENT_STATES,
    ROOT_CAUSES,
    SEGMENTS,
    ActionOutcome,
    ContactEvent,
    ContactWindow,
    GeneratedCase,
    HiddenState,
    HistoricalPayment,
    ObservableContext,
    PaymentFailureEvent,
    SimulatorOutcome,
    SyntheticCustomer,
)
from .simulator import InvalidSeedError, Simulator, is_within_horizon
from .policies import (
    DeterministicPolicy,
    NoInterventionPolicy,
    PolicySelection,
    RetryAllPolicy,
    SimpleRuleBasedPolicy,
    primary_baseline_policies,
)

__all__ = [
    "ACTIONS",
    "ArenaReport",
    "ArenaRunner",
    "CONTACT_ACTIONS",
    "ENVIRONMENT_STATES",
    "ROOT_CAUSES",
    "SEGMENTS",
    "ActionOutcome",
    "ConfigurationError",
    "ContactEvent",
    "ContactWindow",
    "GeneratedCase",
    "HiddenState",
    "HistoricalPayment",
    "InvalidSeedError",
    "InvalidPolicyActionError",
    "is_within_horizon",
    "ObservableContext",
    "PaymentFailureEvent",
    "PolicyDecisionRecord",
    "PolicySelection",
    "DeterministicPolicy",
    "NoInterventionPolicy",
    "RetryAllPolicy",
    "SimpleRuleBasedPolicy",
    "primary_baseline_policies",
    "Simulator",
    "SimulatorConfig",
    "SimulatorOutcome",
    "SyntheticCustomer",
]
