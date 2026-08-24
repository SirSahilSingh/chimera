"""Dependency-light binary metrics and calibration diagnostics."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _validate(labels: np.ndarray, probabilities: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(labels, dtype=np.float64)
    p = np.asarray(probabilities, dtype=np.float64)
    if y.ndim != 1 or p.ndim != 1 or y.shape[0] != p.shape[0] or y.shape[0] == 0:
        raise ValueError("labels and probabilities must be matching non-empty vectors")
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(p)):
        raise ValueError("labels and probabilities must be finite")
    if not np.all(np.isin(y, [0.0, 1.0])):
        raise ValueError("labels must be binary")
    return y, np.clip(p, 0.0, 1.0)


def roc_auc(labels: np.ndarray, probabilities: np.ndarray) -> float | None:
    y, p = _validate(labels, probabilities)
    positive = y == 1.0
    negative = y == 0.0
    if not positive.any() or not negative.any():
        return None
    order = np.argsort(p, kind="mergesort")
    sorted_p = p[order]
    ranks = np.empty_like(sorted_p, dtype=np.float64)
    start = 0
    while start < len(sorted_p):
        end = start + 1
        while end < len(sorted_p) and sorted_p[end] == sorted_p[start]:
            end += 1
        ranks[start:end] = (start + 1 + end) / 2.0
        start = end
    original_ranks = np.empty_like(ranks)
    original_ranks[order] = ranks
    positive_rank_sum = original_ranks[positive].sum()
    n_positive = positive.sum()
    n_negative = negative.sum()
    return float((positive_rank_sum - n_positive * (n_positive + 1) / 2.0) / (n_positive * n_negative))


def pr_auc(labels: np.ndarray, probabilities: np.ndarray) -> float | None:
    y, p = _validate(labels, probabilities)
    positives = int(y.sum())
    if positives == 0:
        return None
    order = np.argsort(-p, kind="mergesort")
    sorted_labels = y[order]
    cumulative_true = np.cumsum(sorted_labels)
    positions = np.arange(1, len(y) + 1, dtype=np.float64)
    precision = cumulative_true / positions
    recall = cumulative_true / positives
    increments = np.diff(np.concatenate(([0.0], recall)))
    return float(np.sum(increments * precision))


def brier_score(labels: np.ndarray, probabilities: np.ndarray) -> float:
    y, p = _validate(labels, probabilities)
    return float(np.mean((p - y) ** 2))


def calibration_curve(labels: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> list[dict[str, Any]]:
    y, p = _validate(labels, probabilities)
    if bins <= 0:
        raise ValueError("bins must be positive")
    result: list[dict[str, Any]] = []
    edges = np.linspace(0.0, 1.0, bins + 1)
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        mask = (p >= lower) & ((p < upper) if index < bins - 1 else (p <= upper))
        count = int(mask.sum())
        result.append(
            {
                "bin": index,
                "lower": float(lower),
                "upper": float(upper),
                "count": count,
                "mean_predicted": float(p[mask].mean()) if count else None,
                "observed_rate": float(y[mask].mean()) if count else None,
            }
        )
    return result


def summarize_predictions(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    y, p = _validate(labels, probabilities)
    return {
        "row_count": int(y.shape[0]),
        "positive_count": int(y.sum()),
        "negative_count": int((1.0 - y).sum()),
        "positive_rate": float(y.mean()),
        "roc_auc": roc_auc(y, p),
        "pr_auc": pr_auc(y, p),
        "brier_score": brier_score(y, p),
        "calibration_curve": calibration_curve(y, p),
    }
