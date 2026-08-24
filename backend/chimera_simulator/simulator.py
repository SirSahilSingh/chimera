"""Deterministic simulator generation and horizon outcome handling."""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import SimulatorConfig
from .context import build_observable_context
from .models import (
    ACTIONS,
    CONTACT_ACTIONS,
    ActionOutcome,
    ContactEvent,
    ContactWindow,
    GeneratedCase,
    HiddenState,
    HistoricalPayment,
    PaymentFailureEvent,
    SimulatorOutcome,
    SyntheticCustomer,
)
from .seeds import InvalidSeedError, derive_seed, event_identity, validate_split_seed

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "simulator_v1.yaml"
UTC = timezone.utc
EVENT_ANCHOR = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    threshold = rng.random()
    cumulative = 0.0
    for key, weight in weights.items():
        cumulative += float(weight)
        if threshold < cumulative:
            return key
    return next(reversed(weights))


def _clamp_probability(value: float) -> float:
    return max(0.01, min(0.99, value))


def is_within_horizon(timestamp: datetime, horizon_start: datetime, horizon_end: datetime) -> bool:
    """Use the frozen half-open outcome interval [start, end)."""

    return horizon_start <= timestamp < horizon_end


class Simulator:
    """Generate a decision-facing event and separate simulator truth."""

    def __init__(self, config: SimulatorConfig | str | Path | None = None) -> None:
        if config is None:
            self.config = SimulatorConfig.from_file(DEFAULT_CONFIG_PATH)
        elif isinstance(config, SimulatorConfig):
            self.config = config
        else:
            self.config = SimulatorConfig.from_file(config)

    def generate_case(self, split: str, seed: int, event_index: int) -> GeneratedCase:
        validate_split_seed(self.config, split, seed)
        if isinstance(event_index, bool) or not isinstance(event_index, int) or event_index < 0:
            raise ValueError("event_index must be a non-negative integer")

        event_id = event_identity(self.config.simulator_version, split, seed, event_index)
        decision_timestamp = EVENT_ANCHOR + timedelta(minutes=event_index)
        distributions = self.config.raw["distributions"]
        segment_rng = random.Random(derive_seed(self.config.simulator_version, split, seed, event_index, "segment"))
        environment_rng = random.Random(derive_seed(self.config.simulator_version, split, seed, event_index, "environment"))
        root_cause_rng = random.Random(derive_seed(self.config.simulator_version, split, seed, event_index, "root_cause"))
        customer_rng = random.Random(derive_seed(self.config.simulator_version, split, seed, event_index, "customer"))
        history_rng = random.Random(derive_seed(self.config.simulator_version, split, seed, event_index, "history"))

        segment = _weighted_choice(segment_rng, distributions["segments"])
        environment = _weighted_choice(environment_rng, distributions["environments"])
        root_cause = self._sample_root_cause(root_cause_rng, segment, environment)
        amount_paise = self._sample_amount(customer_rng)
        natural_probability = float(self.config.raw["outcomes"]["natural_recovery_by_segment"][segment])

        customer = self._generate_customer(customer_rng, split, seed, event_index)
        historical_payments, contacts = self._generate_history(
            history_rng,
            customer,
            decision_timestamp,
            natural_probability,
            split,
            seed,
            event_index,
        )
        context = build_observable_context(
            customer=customer,
            historical_payments=historical_payments,
            prior_contacts=contacts,
            decision_timestamp=decision_timestamp,
            incident_flag=environment != "NORMAL",
            observation_window_days=self.config.observation_window_days,
        )
        payment_method = self._payment_method(customer_rng, root_cause)
        event = PaymentFailureEvent(
            event_id=event_id,
            payment_id=f"pay_{split}_{seed}_{event_index}",
            customer=customer,
            context=context,
            amount_paise=amount_paise,
            currency="INR",
            payment_method=payment_method,
            failure_reason=root_cause,
            source_timestamp=decision_timestamp,
            decision_timestamp=decision_timestamp,
            available_actions=ACTIONS,
            contact_window=self._contact_window(),
            action_is_outbound={
                **{action: action in CONTACT_ACTIONS for action in ACTIONS},
                "HUMAN_OUTREACH": True,
            },
        )
        hidden_state = HiddenState(
            customer_id=customer.customer_id,
            customer_segment=segment,
            environment_state=environment,
            natural_recovery_probability=natural_probability,
            action_responsiveness=dict(self.config.raw["outcomes"]["segment_action_delta"][segment]),
        )
        outcome = self._generate_outcome(event, hidden_state)
        return GeneratedCase(event=event, hidden_state=hidden_state, outcome=outcome)

    def generate_batch(self, split: str, seed: int, count: int) -> tuple[GeneratedCase, ...]:
        validate_split_seed(self.config, split, seed)
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("count must be a positive integer")
        return tuple(self.generate_case(split, seed, event_index) for event_index in range(count))

    def apply_promise_to_pay(
        self,
        case: GeneratedCase,
        promised_date: datetime,
    ) -> GeneratedCase:
        """Represent a valid voice promise without treating intent as recovery."""

        if promised_date.tzinfo is None:
            raise ValueError("promised_date must be timezone-aware")
        promised_date = promised_date.astimezone(UTC)
        outcome = case.outcome
        if not is_within_horizon(promised_date, outcome.horizon_start, outcome.horizon_end):
            raise ValueError("promised_date must fall inside the seven-day outcome horizon")
        voice = outcome.for_action("VOICE_RECOVERY")
        if voice.recovered:
            raise ValueError("cannot apply promise-to-pay after voice recovery")
        updated_voice = replace(
            voice,
            status="PROMISE_TO_PAY_PENDING",
            promise_to_pay_date=promised_date,
            verification_timestamp=promised_date,
            outreach_paused=True,
        )
        updated_actions = tuple(
            updated_voice if action.action == "VOICE_RECOVERY" else action for action in outcome.action_outcomes
        )
        return replace(case, outcome=replace(outcome, action_outcomes=updated_actions))

    def _sample_root_cause(self, rng: random.Random, segment: str, environment: str) -> str:
        base = dict(self.config.raw["distributions"]["root_causes_by_segment"][segment])
        if environment == "NORMAL":
            return _weighted_choice(rng, base)
        override = self.config.raw["distributions"]["environment_root_cause_overrides"][environment]
        forced_root_cause = override["root_cause"]
        if rng.random() < float(override["probability"]):
            return forced_root_cause
        residual = {key: value for key, value in base.items() if key != forced_root_cause}
        total = sum(residual.values())
        return _weighted_choice(rng, {key: value / total for key, value in residual.items()})

    def _sample_amount(self, rng: random.Random) -> int:
        band = _weighted_choice(
            rng,
            {str(index): band["share"] for index, band in enumerate(self.config.raw["distributions"]["amount_bands"])},
        )
        selected = self.config.raw["distributions"]["amount_bands"][int(band)]
        return rng.randint(selected["min_paise"], selected["max_paise"])

    def _generate_customer(self, rng: random.Random, split: str, seed: int, event_index: int) -> SyntheticCustomer:
        first_names = ("Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ishita", "Arjun", "Naina")
        last_names = ("Sharma", "Patel", "Iyer", "Kapoor", "Verma", "Rao", "Sen", "Khan")
        name = f"{rng.choice(first_names)} {rng.choice(last_names)}"
        numeric_id = f"{seed:06d}{event_index:06d}"
        customer_id = f"cust_{split}_{numeric_id}"
        return SyntheticCustomer(
            customer_id=customer_id,
            synthetic_name=name,
            synthetic_phone=f"+91-90000-{(seed + event_index) % 100000:05d}",
            synthetic_email=f"{customer_id.lower()}@example.test",
            language_preference="hinglish" if rng.random() < 0.35 else "english",
            communication_preference="allowed",
            consent_status="synthetic_demo_consent",
            subscription_state="active",
        )

    def _generate_history(
        self,
        rng: random.Random,
        customer: SyntheticCustomer,
        decision_timestamp: datetime,
        natural_probability: float,
        split: str,
        seed: int,
        event_index: int,
    ) -> tuple[tuple[HistoricalPayment, ...], tuple[ContactEvent, ...]]:
        historical_payments: list[HistoricalPayment] = []
        for index, days_ago in enumerate((1, 3, 7, 14)):
            timestamp = decision_timestamp - timedelta(days=days_ago, hours=index)
            historical_payments.append(
                HistoricalPayment(
                    payment_id=f"hist_{split}_{seed}_{event_index}_{index}",
                    source_timestamp=timestamp,
                    amount_paise=self._sample_amount(rng),
                    outcome="succeeded" if rng.random() < natural_probability else "failed",
                    provider_code="synthetic",
                )
            )
        contacts: list[ContactEvent] = []
        for index in range(rng.randint(0, 3)):
            contacts.append(
                ContactEvent(
                    contact_id=f"contact_{split}_{seed}_{event_index}_{index}",
                    source_timestamp=decision_timestamp - timedelta(days=rng.randint(1, 10), hours=index),
                    channel=rng.choice(("message", "voice", "payment_link")),
                    response=rng.choice(("ignored", "read", "willing_to_pay", None)),
                )
            )
        return tuple(historical_payments), tuple(contacts)

    def _payment_method(self, rng: random.Random, root_cause: str) -> str:
        if root_cause == "expired_method":
            return "card"
        return rng.choice(("card", "upi", "netbanking"))

    def _contact_window(self) -> ContactWindow:
        defaults = self.config.raw["policy_defaults"]
        return ContactWindow(
            start_local=defaults["contact_window_start"],
            end_local=defaults["contact_window_end"],
            timezone=defaults["contact_window_timezone"],
            contact_actions=tuple(defaults["contact_actions"]),
        )

    def _generate_outcome(self, event: PaymentFailureEvent, hidden_state: HiddenState) -> SimulatorOutcome:
        outcome_config = self.config.raw["outcomes"]
        segment_deltas = outcome_config["segment_action_delta"][hidden_state.customer_segment]
        root_deltas = outcome_config["root_cause_action_delta"][event.failure_reason]
        environment_deltas = outcome_config["environment_action_delta"][hidden_state.environment_state]
        timing_modifier = float(outcome_config["timing_modifier"])
        horizon_start = event.decision_timestamp
        horizon_end = horizon_start + timedelta(days=self.config.horizon_days)
        action_costs = self.config.action_costs_paise
        incentive_costs = self.config.incentive_costs_paise
        fatigue_base = self.config.fatigue_base_paise
        action_outcomes: list[ActionOutcome] = []
        contacts = event.context.contacts_last_7_days
        for action in ACTIONS:
            probability = _clamp_probability(
                hidden_state.natural_recovery_probability
                + float(segment_deltas[action])
                + float(root_deltas[action])
                + float(environment_deltas[action])
                + timing_modifier
            )
            action_seed = derive_seed(
                self.config.simulator_version,
                event.event_id.split(":")[1],
                int(event.event_id.split(":")[2]),
                int(event.event_id.split(":")[3]),
                action,
            )
            action_rng = random.Random(action_seed)
            recovered = action_rng.random() < probability
            recovery_timestamp = None
            if recovered:
                recovery_timestamp = horizon_start
            status = "RECOVERED" if recovered else "UNRECOVERED"
            fatigue_penalty = fatigue_base[action] * (1 + contacts)
            action_outcomes.append(
                ActionOutcome(
                    action=action,
                    recovery_probability=probability,
                    recovered=recovered,
                    status=status,
                    recovery_timestamp=recovery_timestamp,
                    promise_to_pay_date=None,
                    verification_timestamp=None,
                    outreach_paused=False,
                    action_cost_paise=action_costs[action],
                    incentive_cost_paise=incentive_costs[action],
                    fatigue_penalty_paise=fatigue_penalty,
                )
            )
        return SimulatorOutcome(
            event_id=event.event_id,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            action_outcomes=tuple(action_outcomes),
        )
