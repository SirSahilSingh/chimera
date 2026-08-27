from __future__ import annotations

from collections import Counter
from typing import Iterable


def distribution(values: Iterable[str]) -> dict[str, float]:
    values = list(values)
    if not values:
        return {}
    counts = Counter(values)
    total = len(values)
    return {key: counts[key] / total for key in sorted(counts)}


def absolute_distribution_change(baseline: dict[str, float], current: dict[str, float]) -> float:
    keys = set(baseline) | set(current)
    return sum(abs(current.get(key, 0.0) - baseline.get(key, 0.0)) for key in keys) / 2


def severity(score: float, sample_size: int) -> str:
    if sample_size < 10:
        return "INSUFFICIENT_DATA"
    if score >= 0.25:
        return "HIGH"
    if score >= 0.10:
        return "MEDIUM"
    return "LOW"
