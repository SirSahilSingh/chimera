"""Loading and validation for the frozen simulator configuration."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ACTIONS, CONTACT_ACTIONS, ENVIRONMENT_STATES, ROOT_CAUSES, SEGMENTS, SPLITS


class ConfigurationError(ValueError):
    """Raised when a simulator configuration is missing or invalid."""


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{label} must be an object")
    return value


def _require_probability(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{label} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ConfigurationError(f"{label} must be between 0 and 1")
    return number


def _require_integer_money(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{label} must be an integer paise value")
    if value < 0:
        raise ConfigurationError(f"{label} cannot be negative")
    return value


def _validate_distribution(values: dict[str, Any], expected: tuple[str, ...], label: str) -> None:
    if set(values) != set(expected):
        raise ConfigurationError(f"{label} keys must be exactly {expected}")
    total = sum(_require_probability(values[key], f"{label}.{key}") for key in expected)
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        raise ConfigurationError(f"{label} must sum to 1.0, got {total}")


def _validate_delta_table(table: dict[str, Any], row_keys: tuple[str, ...], label: str) -> None:
    if set(table) != set(row_keys):
        raise ConfigurationError(f"{label} rows must be exactly {row_keys}")
    for row_key in row_keys:
        row = _require_mapping(table[row_key], f"{label}.{row_key}")
        if set(row) != set(ACTIONS):
            raise ConfigurationError(f"{label}.{row_key} must define every action")
        for action, value in row.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigurationError(f"{label}.{row_key}.{action} must be numeric")
            if not -1.0 <= float(value) <= 1.0:
                raise ConfigurationError(f"{label}.{row_key}.{action} must be between -1 and 1")


@dataclass(frozen=True)
class SimulatorConfig:
    raw: dict[str, Any]
    source_path: Path
    config_hash: str

    @classmethod
    def from_file(cls, path: str | Path) -> "SimulatorConfig":
        source_path = Path(path)
        try:
            raw_bytes = source_path.read_bytes()
        except OSError as exc:
            raise ConfigurationError(f"cannot read configuration: {source_path}") from exc
        try:
            raw = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfigurationError(
                "simulator_v1.yaml must contain JSON-compatible YAML; no YAML dependency is required"
            ) from exc
        if not isinstance(raw, dict):
            raise ConfigurationError("configuration root must be an object")
        config = cls(raw=raw, source_path=source_path, config_hash=hashlib.sha256(raw_bytes).hexdigest())
        config.validate()
        return config

    @property
    def simulator_version(self) -> str:
        return str(self.raw["simulator_version"])

    @property
    def horizon_days(self) -> int:
        return int(self.raw["dataset"]["evaluation_horizon_days"])

    @property
    def observation_window_days(self) -> int:
        return int(self.raw["dataset"]["observation_window_days"])

    @property
    def action_costs_paise(self) -> dict[str, int]:
        return dict(self.raw["costs_paise"]["action"])

    @property
    def incentive_costs_paise(self) -> dict[str, int]:
        return dict(self.raw["costs_paise"]["incentive"])

    @property
    def fatigue_base_paise(self) -> dict[str, int]:
        return dict(self.raw["costs_paise"]["fatigue_base"])

    def validate(self) -> None:
        if self.raw.get("schema_version") != 1:
            raise ConfigurationError("schema_version must be 1")
        if self.raw.get("simulator_version") != "simulator_v1.0.0":
            raise ConfigurationError("simulator_version must be simulator_v1.0.0")

        dataset = _require_mapping(self.raw.get("dataset"), "dataset")
        if dataset.get("evaluation_horizon_days") != 7:
            raise ConfigurationError("evaluation_horizon_days must be exactly 7")
        if dataset.get("observation_window_days") != 30:
            raise ConfigurationError("observation_window_days must be exactly 30")
        if not isinstance(dataset.get("default_events"), int) or dataset["default_events"] <= 0:
            raise ConfigurationError("dataset.default_events must be a positive integer")

        distributions = _require_mapping(self.raw.get("distributions"), "distributions")
        _validate_distribution(distributions.get("segments", {}), SEGMENTS, "distributions.segments")
        _validate_distribution(distributions.get("environments", {}), ENVIRONMENT_STATES, "distributions.environments")

        root_causes_by_segment = _require_mapping(
            distributions.get("root_causes_by_segment"), "distributions.root_causes_by_segment"
        )
        if set(root_causes_by_segment) != set(SEGMENTS):
            raise ConfigurationError("root_causes_by_segment must define every customer segment")
        for segment in SEGMENTS:
            _validate_distribution(root_causes_by_segment[segment], ROOT_CAUSES, f"root_causes_by_segment.{segment}")

        amount_bands = distributions.get("amount_bands")
        if not isinstance(amount_bands, list) or not amount_bands:
            raise ConfigurationError("amount_bands must be a non-empty list")
        band_total = 0.0
        previous_max = 0
        for index, band in enumerate(amount_bands):
            band = _require_mapping(band, f"amount_bands[{index}]")
            minimum = _require_integer_money(band.get("min_paise"), f"amount_bands[{index}].min_paise")
            maximum = _require_integer_money(band.get("max_paise"), f"amount_bands[{index}].max_paise")
            if minimum <= previous_max or maximum < minimum:
                raise ConfigurationError("amount bands must be ascending and non-overlapping")
            previous_max = maximum
            band_total += _require_probability(band.get("share"), f"amount_bands[{index}].share")
        if not math.isclose(band_total, 1.0, abs_tol=1e-9):
            raise ConfigurationError("amount band shares must sum to 1.0")

        overrides = _require_mapping(
            distributions.get("environment_root_cause_overrides"),
            "distributions.environment_root_cause_overrides",
        )
        if set(overrides) != {"GATEWAY_DEGRADATION", "ISSUER_NETWORK_DEGRADATION"}:
            raise ConfigurationError("environment root-cause overrides are incomplete")
        for environment, override in overrides.items():
            override = _require_mapping(override, f"environment_root_cause_overrides.{environment}")
            if override.get("root_cause") not in ROOT_CAUSES:
                raise ConfigurationError(f"invalid override root cause for {environment}")
            _require_probability(override.get("probability"), f"environment_root_cause_overrides.{environment}.probability")

        outcomes = _require_mapping(self.raw.get("outcomes"), "outcomes")
        natural = _require_mapping(outcomes.get("natural_recovery_by_segment"), "natural_recovery_by_segment")
        if set(natural) != set(SEGMENTS):
            raise ConfigurationError("natural recovery must define every customer segment")
        for segment, probability in natural.items():
            _require_probability(probability, f"natural_recovery_by_segment.{segment}")
        _validate_delta_table(outcomes.get("segment_action_delta", {}), SEGMENTS, "segment_action_delta")
        _validate_delta_table(outcomes.get("root_cause_action_delta", {}), ROOT_CAUSES, "root_cause_action_delta")
        _validate_delta_table(outcomes.get("environment_action_delta", {}), ENVIRONMENT_STATES, "environment_action_delta")
        timing_modifier = outcomes.get("timing_modifier")
        if isinstance(timing_modifier, bool) or not isinstance(timing_modifier, (int, float)):
            raise ConfigurationError("timing_modifier must be numeric")
        if timing_modifier != 0.0:
            raise ConfigurationError("simulator_v1.0.0 timing_modifier must be 0.0")

        costs = _require_mapping(self.raw.get("costs_paise"), "costs_paise")
        for cost_key in ("action", "incentive", "fatigue_base"):
            cost_table = _require_mapping(costs.get(cost_key), f"costs_paise.{cost_key}")
            if set(cost_table) != set(ACTIONS):
                raise ConfigurationError(f"costs_paise.{cost_key} must define every action")
            for action, value in cost_table.items():
                _require_integer_money(value, f"costs_paise.{cost_key}.{action}")

        policy_defaults = _require_mapping(self.raw.get("policy_defaults"), "policy_defaults")
        for key in ("max_retries", "max_contacts_per_7_days", "approval_threshold_paise"):
            if key.endswith("paise"):
                _require_integer_money(policy_defaults.get(key), f"policy_defaults.{key}")
            elif not isinstance(policy_defaults.get(key), int) or policy_defaults[key] < 0:
                raise ConfigurationError(f"policy_defaults.{key} must be a non-negative integer")
        _require_probability(policy_defaults.get("low_confidence_threshold"), "policy_defaults.low_confidence_threshold")
        contact_actions = policy_defaults.get("contact_actions")
        if tuple(contact_actions or ()) != CONTACT_ACTIONS:
            raise ConfigurationError("policy_defaults.contact_actions must match the documented contact actions")
        for key in ("contact_window_start", "contact_window_end", "contact_window_timezone"):
            if not isinstance(policy_defaults.get(key), str) or not policy_defaults[key]:
                raise ConfigurationError(f"policy_defaults.{key} must be a non-empty string")
        if not isinstance(policy_defaults.get("voice_enabled"), bool):
            raise ConfigurationError("policy_defaults.voice_enabled must be boolean")

        seed = _require_mapping(self.raw.get("seed"), "seed")
        if seed.get("derivation") != "simulator_version + split + seed + event_index + action_type":
            raise ConfigurationError("seed derivation does not match the frozen scheme")
        ranges = _require_mapping(seed.get("ranges"), "seed.ranges")
        if set(ranges) != set(SPLITS):
            raise ConfigurationError("seed ranges must define every split")
        seen: list[tuple[int, int, str]] = []
        for split in SPLITS:
            value = ranges[split]
            if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, int) for item in value):
                raise ConfigurationError(f"seed.ranges.{split} must be [min, max]")
            minimum, maximum = value
            if minimum < 0 or maximum < minimum:
                raise ConfigurationError(f"invalid seed range for {split}")
            for prior_min, prior_max, prior_split in seen:
                if minimum <= prior_max and prior_min <= maximum:
                    raise ConfigurationError(f"seed ranges overlap: {split} and {prior_split}")
            seen.append((minimum, maximum, split))
