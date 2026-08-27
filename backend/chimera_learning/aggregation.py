from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


ACTIONS = (
    "RETRY_NOW", "RETRY_LATER", "PAYMENT_LINK", "SEND_MESSAGE",
    "VOICE_RECOVERY", "ESCALATE", "DO_NOTHING",
)


TERMINAL_OUTCOMES = {"RECOVERED", "NOT_RECOVERED", "FAILED", "EXPIRED"}
TERMINAL_CASE_STATUSES = {"RECOVERED", "UNRECOVERED", "CLOSED"}


@dataclass(frozen=True)
class ProviderRecord:
    provider: str
    provider_mode: str
    kind: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    failure_code: str | None = None
    suppressed: bool = False


@dataclass(frozen=True)
class LearningCase:
    case: Any
    decision: Any | None
    selected_candidate: Any | None
    intervention: Any | None
    outcome: Any | None
    providers: tuple[ProviderRecord, ...]

    @property
    def selected_action(self) -> str | None:
        return self.decision.selected_action if self.decision else None

    @property
    def recovered(self) -> bool:
        return bool(self.outcome and self.outcome.status == "RECOVERED") or self.case.status == "RECOVERED"

    @property
    def completed(self) -> bool:
        return self.recovered or bool(self.outcome and self.outcome.status in TERMINAL_OUTCOMES - {"RECOVERED"}) or self.case.status in TERMINAL_CASE_STATUSES - {"RECOVERED"}

    @property
    def outcome_status(self) -> str:
        if self.recovered:
            return "RECOVERED"
        if self.outcome and self.outcome.status in TERMINAL_OUTCOMES:
            return self.outcome.status
        if self.case.status in TERMINAL_CASE_STATUSES:
            return self.case.status
        return "PENDING"

    @property
    def recovered_amount_paise(self) -> int:
        return int(self.outcome.recovered_amount_paise or 0) if self.recovered and self.outcome else 0


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _outcome_distribution(rows: Iterable[LearningCase]) -> dict[str, int]:
    return dict(sorted(Counter(row.outcome_status for row in rows).items()))


def _action_distribution(rows: Iterable[LearningCase]) -> dict[str, int]:
    counts = Counter(row.selected_action for row in rows if row.selected_action)
    return {action: counts.get(action, 0) for action in ACTIONS}


def _net_value(row: LearningCase) -> int:
    if not row.recovered:
        return 0
    candidate = row.selected_candidate
    cost = (candidate.action_cost_paise + candidate.incentive_cost_paise + candidate.fatigue_penalty_paise) if candidate else 0
    return row.recovered_amount_paise - cost


def overall(rows: list[LearningCase]) -> dict:
    completed = [row for row in rows if row.completed]
    recovered = [row for row in completed if row.recovered]
    unrecovered = [row for row in completed if not row.recovered]
    pending = [row for row in rows if not row.completed]
    durations = []
    for row in completed:
        if row.outcome and row.outcome.occurred_at:
            start = row.case.decision_timestamp
            end = row.outcome.occurred_at
            duration = (end - start).total_seconds()
            if duration >= 0:
                durations.append(duration)
    modes = {record.provider_mode for row in rows for record in row.providers}
    return {
        "total_cases": len(rows), "completed_cases": len(completed), "recovered_cases": len(recovered),
        "unrecovered_cases": len(unrecovered), "pending_cases": len(pending),
        "recovery_rate": _rate(len(recovered), len(completed)),
        "gross_recovered_amount_paise": sum(row.recovered_amount_paise for row in recovered),
        "net_recovered_amount_paise": sum(_net_value(row) for row in recovered),
        "average_recovered_value_paise": _rate(sum(row.recovered_amount_paise for row in recovered), len(recovered)),
        "average_time_to_outcome_seconds": _rate(int(sum(durations)), len(durations)),
        "provider_modes": sorted({record.provider_mode for row in rows for record in row.providers}),
        "data_warning": "Demo / non-production outcome data" if rows and "LIVE" not in modes else "INSUFFICIENT_DATA" if not rows else None,
    }


def failures(rows: list[LearningCase]) -> list[dict]:
    output = []
    for reason in sorted({row.case.failure_reason for row in rows}):
        group = [row for row in rows if row.case.failure_reason == reason]
        completed = [row for row in group if row.completed]
        recovered = [row for row in completed if row.recovered]
        actions = {}
        for action in ACTIONS:
            action_rows = [row for row in group if row.selected_action == action]
            action_completed = [row for row in action_rows if row.completed]
            action_recovered = [row for row in action_completed if row.recovered]
            actions[action] = {"count": len(action_rows), "completed_count": len(action_completed), "recovery_rate": _rate(len(action_recovered), len(action_completed))}
        candidates = [(action, value["recovery_rate"]) for action, value in actions.items() if value["recovery_rate"] is not None]
        best_action, best_rate = max(candidates, key=lambda item: (item[1], -ACTIONS.index(item[0]))) if candidates else (None, None)
        probs = [row.decision.predicted_probability for row in group if row.decision]
        nets = [row.decision.expected_net_value_paise for row in group if row.decision]
        output.append({"failure_reason": reason, "case_count": len(group), "completed_count": len(completed), "recovery_rate": _rate(len(recovered), len(completed)), "selected_action_distribution": _action_distribution(group), "recovered_value_paise": sum(row.recovered_amount_paise for row in recovered), "average_predicted_probability": _rate(sum(probs), len(probs)), "average_expected_net_value_paise": _rate(sum(nets), len(nets)), "final_outcome_distribution": _outcome_distribution(group), "action_metrics": actions, "best_action": best_action, "best_action_recovery_rate": best_rate})
    return output


def actions(rows: list[LearningCase]) -> list[dict]:
    output = []
    for action in ACTIONS:
        group = [row for row in rows if row.selected_action == action]
        completed = [row for row in group if row.completed]
        recovered = [row for row in completed if row.recovered]
        candidates = [row.selected_candidate for row in group if row.selected_candidate]
        output.append({"action": action, "selection_count": len(group), "selection_rate": _rate(len(group), len(rows)), "completed_count": len(completed), "recovery_rate": _rate(len(recovered), len(completed)), "gross_recovered_value_paise": sum(row.recovered_amount_paise for row in recovered), "net_recovered_value_paise": sum(_net_value(row) for row in recovered), "average_predicted_probability": _rate(sum(row.decision.predicted_probability for row in group if row.decision), len([row for row in group if row.decision])), "average_expected_net_value_paise": _rate(sum(row.decision.expected_net_value_paise for row in group if row.decision), len([row for row in group if row.decision])), "average_intervention_cost_paise": _rate(sum(candidate.action_cost_paise for candidate in candidates), len(candidates)), "average_fatigue_penalty_paise": _rate(sum(candidate.fatigue_penalty_paise for candidate in candidates), len(candidates)), "outcome_distribution": _outcome_distribution(group), "reliability": "INSUFFICIENT_DATA" if len(completed) == 0 else "LOW_SAMPLE" if len(completed) < 10 else "OBSERVATIONAL"})
    return output


def funnel(rows: list[LearningCase]) -> dict:
    stages = ["CASE_CREATED", "DECISION_CREATED", "INTERVENTION_CREATED", "EXECUTION_ATTEMPTED", "PROVIDER_ACCEPTED", "CUSTOMER_RESPONDED", "PAYMENT_PENDING", "RECOVERED"]
    applicable: dict[str, list[LearningCase]] = {stage: [] for stage in stages}
    completed: dict[str, list[LearningCase]] = {stage: [] for stage in stages}
    for row in rows:
        applicable["CASE_CREATED"].append(row); completed["CASE_CREATED"].append(row)
        if row.decision:
            applicable["DECISION_CREATED"].append(row); completed["DECISION_CREATED"].append(row)
        if row.intervention:
            applicable["INTERVENTION_CREATED"].append(row); completed["INTERVENTION_CREATED"].append(row)
        if row.selected_action and row.selected_action != "DO_NOTHING":
            applicable["EXECUTION_ATTEMPTED"].append(row)
            if row.providers or (row.intervention and row.intervention.executions): completed["EXECUTION_ATTEMPTED"].append(row)
            if row.providers and any(record.status not in {"FAILED", "ERROR"} for record in row.providers): completed["PROVIDER_ACCEPTED"].append(row)
        if row.selected_action in {"VOICE_RECOVERY"}:
            applicable["CUSTOMER_RESPONDED"].append(row)
            if row.intervention and any(getattr(call, "turns", None) and any(turn.speaker == "customer" for turn in call.turns) for call in getattr(row.intervention, "voice_calls", [])): completed["CUSTOMER_RESPONDED"].append(row)
        if row.selected_action in {"PAYMENT_LINK", "SEND_MESSAGE", "VOICE_RECOVERY", "RETRY_NOW", "RETRY_LATER"}:
            applicable["PAYMENT_PENDING"].append(row)
            if row.outcome and row.outcome.status == "PENDING": completed["PAYMENT_PENDING"].append(row)
        if row.recovered:
            applicable["RECOVERED"].append(row); completed["RECOVERED"].append(row)
    stage_rows = []
    for stage in stages:
        entered = len(applicable[stage]); done = len(completed[stage])
        stage_rows.append({"stage": stage, "entered": entered, "completed": done, "not_applicable": len(rows) - entered, "drop_off_rate": _rate(entered - done, entered), "status": "OBSERVATIONAL" if entered else "NOT_APPLICABLE"})
    bottlenecks = [row for row in stage_rows if row["drop_off_rate"] is not None and row["drop_off_rate"] > 0]
    bottleneck = max(bottlenecks, key=lambda row: (row["drop_off_rate"], row["entered"])) if bottlenecks else None
    if bottleneck:
        bottleneck = dict(bottleneck); bottleneck["statement"] = f"{bottleneck['stage'].replace('_', ' ').title()} is the largest observed funnel drop-off."
    return {"stages": stage_rows, "largest_bottleneck": bottleneck}


def providers(rows: list[LearningCase]) -> list[dict]:
    grouped: dict[tuple[str, str], list[ProviderRecord]] = defaultdict(list)
    for row in rows:
        for record in row.providers:
            grouped[(record.provider, record.provider_mode)].append(record)
    output = []
    for (provider, mode), records in sorted(grouped.items()):
        latencies = [(record.completed_at - record.started_at).total_seconds() for record in records if record.started_at and record.completed_at]
        attempts = [record for record in records if not record.suppressed and record.kind != "webhook"]
        output.append({"provider": provider, "provider_mode": mode, "attempt_count": len(attempts), "successful_requests": sum(record.status not in {"FAILED", "ERROR"} for record in attempts), "failed_requests": sum(record.status in {"FAILED", "ERROR"} for record in attempts), "timeout_count": sum(record.failure_code == "provider_timeout" for record in attempts), "retry_count": sum(record.kind == "retry" for record in attempts), "duplicate_suppression_count": sum(record.suppressed for record in records), "average_latency_seconds": _rate(sum(latencies), len(latencies)), "final_recovery_count": sum(row.recovered for row in rows if any(item.provider == provider and item.provider_mode == mode for item in row.providers)), "reliability": "LOW_SAMPLE" if len(attempts) < 10 else "OBSERVATIONAL"})
    return output
