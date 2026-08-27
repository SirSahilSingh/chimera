from __future__ import annotations


def generate_insights(report: dict) -> list[dict]:
    insights: list[dict] = []
    actions = report.get("actions", [])
    failures = report.get("failures", [])
    for row in actions:
        if row["selection_count"] < 10:
            insights.append({"category": "WARNING", "severity": "LOW", "title": f"{row['action']} has a small sample", "evidence": f"{row['selection_count']} selected cases", "sample_size": row["selection_count"], "reliability": "LOW_SAMPLE", "limitation": "Observed performance is not yet reliable."})
    for row in failures:
        if row.get("completed_count", 0) >= 10 and row.get("best_action"):
            insights.append({"category": "POSITIVE", "severity": "INFO", "title": f"{row['best_action']} leads {row['failure_reason']} recovery", "evidence": f"Observed recovery rate {row['best_action_recovery_rate']:.2%}", "sample_size": row["completed_count"], "reliability": "OBSERVATIONAL", "limitation": "This is persisted local/demo outcome data, not real-world performance."})
    calibration = report.get("calibration", {})
    if calibration.get("sample_size", 0) >= 10 and abs(calibration.get("calibration_gap", 0.0)) >= 0.10:
        insights.append({"category": "CALIBRATION", "severity": "WARNING", "title": "Observed recovery differs materially from stored predictions", "evidence": f"Calibration gap {calibration['calibration_gap']:.2%}", "sample_size": calibration["sample_size"], "reliability": "OBSERVATIONAL", "limitation": "No model coefficients or probabilities were changed."})
    funnel = report.get("funnel", {})
    bottleneck = funnel.get("largest_bottleneck")
    if bottleneck:
        insights.append({"category": "OPERATIONAL", "severity": "WARNING", "title": bottleneck["statement"], "evidence": f"Drop-off rate {bottleneck['drop_off_rate']:.2%}", "sample_size": bottleneck["entered"], "reliability": "OBSERVATIONAL", "limitation": "Only persisted lifecycle stages are included."})
    for provider in report.get("providers", []):
        if provider["provider_mode"] in {"LOCAL", "MOCK", "TEST"}:
            insights.append({"category": "PROVIDER", "severity": "INFO", "title": f"{provider['provider_mode']} provider data is non-production", "evidence": f"{provider['attempt_count']} persisted provider records", "sample_size": provider["attempt_count"], "reliability": "OBSERVATIONAL", "limitation": "Do not interpret this as LIVE provider performance."})
    return insights
