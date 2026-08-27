from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import (
    Decision, Intervention, LearningReport, MessageAttempt, PaymentLink,
    RecoveryCase, RetryAttempt, VoiceCall,
)
from .aggregation import LearningCase, ProviderRecord, actions, failures, funnel, overall, providers
from .calibration import calibration_report
from .drift import absolute_distribution_change, distribution, severity
from .insights import generate_insights
from .recommendations import generate_recommendations
from .schemas import LearningReportType
from .validation import validate_learning_payload
from .versions import LEARNING_ANALYSIS_VERSION


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class LearningService:
    """Builds analytical reports from stored records without decision authority."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _load(self, provider_mode: str | None = None) -> list[LearningCase]:
        cases = list(self.session.scalars(select(RecoveryCase).order_by(RecoveryCase.created_at.asc(), RecoveryCase.id.asc())))
        decisions = list(self.session.scalars(select(Decision).options(selectinload(Decision.candidates)).order_by(Decision.created_at.asc(), Decision.id.asc())))
        interventions = list(self.session.scalars(select(Intervention).options(
            selectinload(Intervention.outcomes), selectinload(Intervention.executions),
            selectinload(Intervention.voice_calls).selectinload(VoiceCall.turns),
        )))
        payments = list(self.session.scalars(select(PaymentLink).options(selectinload(PaymentLink.events))))
        messages = list(self.session.scalars(select(MessageAttempt).options(selectinload(MessageAttempt.events))))
        retries = list(self.session.scalars(select(RetryAttempt)))
        decision_by_case: dict[str, Decision] = {}
        for decision in decisions:
            if decision.recovery_case_id not in decision_by_case or (decision.created_at, decision.id) > (decision_by_case[decision.recovery_case_id].created_at, decision_by_case[decision.recovery_case_id].id):
                decision_by_case[decision.recovery_case_id] = decision
        intervention_by_case: dict[str, Intervention] = {}
        for intervention in interventions:
            if intervention.recovery_case_id not in intervention_by_case or (intervention.created_at, intervention.id) > (intervention_by_case[intervention.recovery_case_id].created_at, intervention_by_case[intervention.recovery_case_id].id):
                intervention_by_case[intervention.recovery_case_id] = intervention
        payments_by_case: dict[str, list[PaymentLink]] = defaultdict(list)
        messages_by_case: dict[str, list[MessageAttempt]] = defaultdict(list)
        retries_by_case: dict[str, list[RetryAttempt]] = defaultdict(list)
        for row in payments: payments_by_case[row.recovery_case_id].append(row)
        for row in messages: messages_by_case[row.recovery_case_id].append(row)
        for row in retries: retries_by_case[row.recovery_case_id].append(row)
        output = []
        for case in cases:
            decision = decision_by_case.get(case.id)
            intervention = intervention_by_case.get(case.id)
            outcome = None
            if intervention and intervention.outcomes:
                outcome = sorted(intervention.outcomes, key=lambda row: (_aware(row.occurred_at), row.id))[-1]
            candidate = next((row for row in decision.candidates if row.action == decision.selected_action), None) if decision else None
            provider_rows: list[ProviderRecord] = []
            for row in payments_by_case[case.id]:
                provider_rows.append(ProviderRecord(row.provider, row.provider_mode, "payment", row.status, row.created_at, row.updated_at, None))
                provider_rows.extend(ProviderRecord(row.provider, row.provider_mode, "webhook", event.status, event.created_at, event.created_at, None, event.payload_json.get("processing_result") in {"ignored_terminal_state", "duplicate"}) for event in row.events)
            for row in messages_by_case[case.id]:
                provider_rows.append(ProviderRecord(row.provider, row.provider_mode, "message", row.status, row.created_at, row.sent_at, None))
                provider_rows.extend(ProviderRecord(row.provider, row.provider_mode, "webhook", event.delivery_state, event.created_at, event.created_at, None, event.payload_json.get("processing_result") in {"ignored_terminal_state", "duplicate"}) for event in row.events)
            for row in retries_by_case[case.id]:
                provider_rows.append(ProviderRecord(row.provider, row.provider_mode, "retry", row.status, row.started_at, row.completed_at, row.validated_result_json.get("error_code")))
            if intervention:
                for call in intervention.voice_calls:
                    provider_rows.append(ProviderRecord(call.provider, call.provider_mode, "voice", call.status, call.created_at, call.completed_at, call.failure_code))
            if provider_mode and not any(record.provider_mode == provider_mode for record in provider_rows):
                continue
            output.append(LearningCase(case, decision, candidate, intervention, outcome, tuple(provider_rows)))
        return output

    def _metadata(self, rows: list[LearningCase], provider_mode: str | None) -> dict:
        modes = {record.provider_mode for row in rows for record in row.providers}
        return {
            "analysis_version": LEARNING_ANALYSIS_VERSION,
            "provider_mode_filter": provider_mode,
            "provider_modes": sorted({record.provider_mode for row in rows for record in row.providers}),
            "sample_size": len(rows),
            "data_warning": "Demo / non-production outcome data" if rows and "LIVE" not in modes else "INSUFFICIENT_DATA" if not rows else None,
        }

    def _base(self, provider_mode: str | None = None) -> dict:
        rows = self._load(provider_mode)
        calibration_rows = [(row.decision.predicted_probability, row.recovered) for row in rows if row.decision and row.completed]
        result = self._metadata(rows, provider_mode)
        result.update({"overall": overall(rows), "actions": actions(rows), "failures": failures(rows), "calibration": calibration_report(calibration_rows)})
        result["insights"] = generate_insights(result)
        result["recommendations"] = generate_recommendations(result["insights"])
        return result

    def overview(self, provider_mode: str | None = None) -> dict:
        return self._base(provider_mode)

    def action_report(self, provider_mode: str | None = None) -> dict:
        rows = self._load(provider_mode); return {**self._metadata(rows, provider_mode), "actions": actions(rows)}

    def failure_report(self, provider_mode: str | None = None) -> dict:
        rows = self._load(provider_mode); return {**self._metadata(rows, provider_mode), "failures": failures(rows)}

    def funnel_report(self, provider_mode: str | None = None) -> dict:
        rows = self._load(provider_mode); return {**self._metadata(rows, provider_mode), "funnel": funnel(rows)}

    def provider_report(self, provider_mode: str | None = None) -> dict:
        rows = self._load(provider_mode); return {**self._metadata(rows, provider_mode), "providers": providers(rows)}

    def calibration(self, provider_mode: str | None = None) -> dict:
        rows = self._load(provider_mode); return {**self._metadata(rows, provider_mode), "calibration": calibration_report([(row.decision.predicted_probability, row.recovered) for row in rows if row.decision and row.completed])}

    def drift(self, provider_mode: str | None = None, baseline_days: int = 30, current_days: int = 7) -> dict:
        rows = self._load(provider_mode)
        timestamps = [_aware(row.case.created_at) for row in rows]
        if not timestamps:
            return {**self._metadata(rows, provider_mode), "status": "INSUFFICIENT_DATA", "metrics": []}
        anchor = max(timestamps)
        current_start = anchor - timedelta(days=current_days)
        baseline_start = current_start - timedelta(days=baseline_days)
        baseline = [row for row in rows if baseline_start <= _aware(row.case.created_at) < current_start]
        current = [row for row in rows if current_start <= _aware(row.case.created_at) <= anchor]
        if len(baseline) < 10 or len(current) < 10:
            return {**self._metadata(rows, provider_mode), "status": "INSUFFICIENT_DATA", "baseline_sample_size": len(baseline), "current_sample_size": len(current), "metrics": []}
        specs = {
            "failure_reason": (lambda row: row.case.failure_reason),
            "payment_method": (lambda row: row.case.payment_method),
            "incident_flag": (lambda row: str(row.case.incident_flag).lower()),
            "selected_action": (lambda row: row.selected_action or "NONE"),
        }
        metrics = []
        for name, getter in specs.items():
            before, after = distribution(getter(row) for row in baseline), distribution(getter(row) for row in current)
            score = absolute_distribution_change(before, after)
            metrics.append({"metric": name, "baseline_window": [baseline_start.isoformat(), current_start.isoformat()], "current_window": [current_start.isoformat(), anchor.isoformat()], "baseline_distribution": before, "current_distribution": after, "drift_score": score, "severity": severity(score, min(len(baseline), len(current))), "baseline_sample_size": len(baseline), "current_sample_size": len(current)})
        prediction_baseline = [row for row in baseline if row.decision is not None]
        prediction_current = [row for row in current if row.decision is not None]
        prediction_getter = lambda row: str(min(9, max(0, int(row.decision.predicted_probability * 10))))
        prediction_before = distribution(prediction_getter(row) for row in prediction_baseline)
        prediction_after = distribution(prediction_getter(row) for row in prediction_current)
        prediction_score = absolute_distribution_change(prediction_before, prediction_after)
        metrics.append({"metric": "predicted_probability_bucket", "baseline_window": [baseline_start.isoformat(), current_start.isoformat()], "current_window": [current_start.isoformat(), anchor.isoformat()], "baseline_distribution": prediction_before, "current_distribution": prediction_after, "drift_score": prediction_score, "severity": severity(prediction_score, min(len(prediction_baseline), len(prediction_current))), "baseline_sample_size": len(prediction_baseline), "current_sample_size": len(prediction_current)})
        before_rate = sum(row.recovered for row in baseline) / len(baseline); after_rate = sum(row.recovered for row in current) / len(current)
        metrics.append({"metric": "recovery_rate", "baseline_value": before_rate, "current_value": after_rate, "drift_score": abs(after_rate - before_rate), "severity": severity(abs(after_rate - before_rate), min(len(baseline), len(current))), "baseline_sample_size": len(baseline), "current_sample_size": len(current)})
        return {**self._metadata(rows, provider_mode), "status": "OBSERVATIONAL", "baseline_sample_size": len(baseline), "current_sample_size": len(current), "metrics": metrics}

    def insights(self, provider_mode: str | None = None) -> dict:
        report = self._base(provider_mode); return {**self._metadata(self._load(provider_mode), provider_mode), "insights": report["insights"]}

    def recommendations(self, provider_mode: str | None = None) -> dict:
        report = self._base(provider_mode); return {**self._metadata(self._load(provider_mode), provider_mode), "recommendations": report["recommendations"]}

    def report(self, report_type: LearningReportType, provider_mode: str | None = None, baseline_days: int = 30, current_days: int = 7) -> dict:
        return {
            LearningReportType.OVERVIEW: self.overview,
            LearningReportType.ACTIONS: self.action_report,
            LearningReportType.FAILURES: self.failure_report,
            LearningReportType.FUNNEL: self.funnel_report,
            LearningReportType.PROVIDERS: self.provider_report,
            LearningReportType.CALIBRATION: self.calibration,
            LearningReportType.DRIFT: lambda mode: self.drift(mode, baseline_days, current_days),
            LearningReportType.INSIGHTS: self.insights,
            LearningReportType.RECOMMENDATIONS: self.recommendations,
        }[report_type](provider_mode)

    def persist_report(self, report_type: LearningReportType, provider_mode: str | None = None, baseline_days: int = 30, current_days: int = 7) -> LearningReport:
        report = self.report(report_type, provider_mode, baseline_days, current_days)
        validate_learning_payload(report)
        input_material = [{"id": row.case.id, "updated_at": str(row.case.updated_at)} for row in self._load(provider_mode)]
        input_hash = hashlib.sha256(_canonical(input_material).encode()).hexdigest()
        output_hash = hashlib.sha256(_canonical(report).encode()).hexdigest()
        row = LearningReport(report_type=report_type.value, analysis_version=LEARNING_ANALYSIS_VERSION, baseline_window=f"{baseline_days}d", current_window=f"{current_days}d", input_hash=input_hash, output_hash=output_hash, structured_report=report)
        self.session.add(row); self.session.commit(); self.session.refresh(row)
        return row

    def list_reports(self) -> list[LearningReport]:
        return list(self.session.scalars(select(LearningReport).order_by(LearningReport.generated_at.desc(), LearningReport.id.desc())))

    def get_report(self, report_id: str) -> LearningReport | None:
        return self.session.get(LearningReport, report_id)
