"""Versioned deterministic configuration for the CHIMERA engine."""

from __future__ import annotations

from dataclasses import dataclass

from backend.chimera_simulator.models import ACTIONS


@dataclass(frozen=True)
class DecisionEngineConfig:
    engine_version: str = "chimera_engine_v1.0.0"
    compatible_model_version: str = "recovery_model_v1.0.0"
    compatible_simulator_version: str = "simulator_v1.0.0"
    compatible_feature_schema_version: str = "features_v1.0.0"
    tie_tolerance_paise: int = 1
    friction_order: tuple[str, ...] = (
        "DO_NOTHING",
        "RETRY_LATER",
        "RETRY_NOW",
        "PAYMENT_LINK",
        "SEND_MESSAGE",
        "VOICE_RECOVERY",
        "ESCALATE",
    )
    action_order: tuple[str, ...] = ACTIONS

    def validate(self) -> None:
        if self.tie_tolerance_paise < 0:
            raise ValueError("tie_tolerance_paise must be non-negative")
        if set(self.friction_order) != set(ACTIONS):
            raise ValueError("friction_order must contain every simulator action exactly once")
        if self.action_order != ACTIONS:
            raise ValueError("action_order must match the frozen simulator action order")
