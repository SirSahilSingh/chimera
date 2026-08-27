from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def calibration_report(rows: Iterable[tuple[float, bool]]) -> dict:
    values = list(rows)
    if not values:
        return {"status": "INSUFFICIENT_DATA", "sample_size": 0, "average_predicted": None, "observed_recovery_rate": None, "calibration_gap": None, "brier_score": None, "reliability_buckets": []}
    average_predicted = sum(probability for probability, _ in values) / len(values)
    observed = sum(int(recovered) for _, recovered in values) / len(values)
    buckets: dict[int, list[tuple[float, bool]]] = defaultdict(list)
    for probability, recovered in values:
        buckets[min(9, max(0, int(probability * 10)))].append((probability, recovered))
    reliability = []
    for bucket in sorted(buckets):
        bucket_rows = buckets[bucket]
        reliability.append({
            "bucket": f"{bucket / 10:.1f}-{(bucket + 1) / 10:.1f}",
            "sample_size": len(bucket_rows),
            "average_predicted": sum(p for p, _ in bucket_rows) / len(bucket_rows),
            "observed_recovery_rate": sum(int(y) for _, y in bucket_rows) / len(bucket_rows),
            "reliability": "LOW_SAMPLE" if len(bucket_rows) < 10 else "OBSERVATIONAL",
        })
    return {
        "status": "OBSERVATIONAL",
        "sample_size": len(values),
        "average_predicted": average_predicted,
        "observed_recovery_rate": observed,
        "calibration_gap": observed - average_predicted,
        "brier_score": sum((p - int(y)) ** 2 for p, y in values) / len(values),
        "reliability_buckets": reliability,
    }
