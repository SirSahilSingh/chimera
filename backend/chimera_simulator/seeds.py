"""Seed-range validation and deterministic seed derivation."""

from __future__ import annotations

import hashlib

from .config import SimulatorConfig
from .models import SPLITS


class InvalidSeedError(ValueError):
    """Raised when a seed is not valid for the requested split."""


def validate_split_seed(config: SimulatorConfig, split: str, seed: int) -> None:
    if split not in SPLITS:
        raise InvalidSeedError(f"unknown split: {split}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise InvalidSeedError("seed must be an integer")
    minimum, maximum = config.raw["seed"]["ranges"][split]
    if not minimum <= seed <= maximum:
        raise InvalidSeedError(f"seed {seed} is not valid for split {split} ({minimum}-{maximum})")


def derive_seed(
    simulator_version: str,
    split: str,
    seed: int,
    event_index: int,
    action_type: str,
) -> int:
    material = f"{simulator_version}|{split}|{seed}|{event_index}|{action_type}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def event_identity(simulator_version: str, split: str, seed: int, event_index: int) -> str:
    return f"{simulator_version}:{split}:{seed}:{event_index}"
