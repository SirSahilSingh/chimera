from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.db.models import Decision, DecisionCandidate, RecoveryCase
from backend.app.main import create_app
from backend.chimera_intelligence.diagnosis import build_detection
from backend.chimera_intelligence.root_cause import analyze_root_cause
from backend.chimera_intelligence.schemas import RecoveryIntelligenceResponse
from backend.chimera_intelligence.service import RecoveryIntelligenceService


CONFIG = SimpleNamespace(raw={"policy_defaults": {"contact_window_start": "08:00", "contact_window_end": "19:00"}})


def journey(*, reason: str = "technical_degradation", incident: bool = True, status: str = "NEW") -> dict:
    return {
        "case": {
            "id": "case-1", "external_event_id": "event-1", "payment_id": "payment-1", "customer_id": "synthetic-1",
            "amount_paise": 166508, "currency": "INR", "failure_reason": reason, "incident_flag": incident,
            "payment_method": "card", "decision_timestamp": "2026-08-26T10:00:00+00:00", "status": status,
        },
        "decision": {
            "selected_action": "RETRY_LATER", "expected_net_value_paise": 5000,
            "trace_json": {"highest_probability_action": "PAYMENT_LINK", "cost_changed_winner": True, "fatigue_changed_winner": False, "constraint_changed_winner": False, "observable_facts": {"contacts_last_7_days": 1}},
            "candidates": [
                {"action": "RETRY_LATER", "status": "PERMISSIBLE", "predicted_probability": 0.5, "expected_net_value_paise": 5000, "blocked_reason": None},
                {"action": "PAYMENT_LINK", "status": "BLOCKED", "predicted_probability": 0.7, "expected_net_value_paise": 4500, "blocked_reason": "outside_contact_window"},
            ],
        },
        "interventions": [{"action": "RETRY_LATER", "status": "AWAITING_OUTCOME", "executions": [{"status": "ACCEPTED", "provider_mode": "LOCAL"}], "outcomes": []}],
        "payments": [], "messages": [], "retries": [], "scheduled_retries": [], "voice_calls": [], "escalations": [],
        "latest_explanation": None, "audit_trail": [{"id": "audit-1", "event_type": "CASE_CREATED", "timestamp": "2026-08-26T10:00:00+00:00", "source": "system"}],
    }


class FakeJourneyService:
    def __init__(self, value: dict):
        self.value = value
        self.calls = 0

    def get(self, case_id: str) -> dict:
        self.calls += 1
        return self.value


class RecoveryIntelligenceTests(unittest.TestCase):
    def test_detection_and_diagnosis_are_observable_and_deterministic(self) -> None:
        first = build_detection(journey(), CONFIG)
        second = build_detection(journey(), CONFIG)
        self.assertEqual(first, second)
        self.assertEqual(first.severity, "high")
        self.assertEqual(analyze_root_cause(first).primary_cause, "TECHNICAL_INCIDENT")
        self.assertNotIn("hidden_state", first.model_dump_json())

    def test_supported_failure_reasons_map_to_honest_categories(self) -> None:
        expected = {
            "expired_method": "EXPIRED_PAYMENT_METHOD",
            "insufficient_funds": "INSUFFICIENT_FUNDS",
            "issuer_decline": "ISSUER_DECLINE",
            "abandonment": "CUSTOMER_ABANDONMENT",
            "other": "UNKNOWN_OR_OTHER",
        }
        for reason, category in expected.items():
            source = journey(reason=reason, incident=False)
            if reason == "other":
                source["decision"]["trace_json"]["observable_facts"] = {}
            detection = build_detection(source, CONFIG)
            self.assertEqual(analyze_root_cause(detection).primary_cause, category)

    def test_service_does_not_recompute_or_mutate(self) -> None:
        source = journey()
        fake = FakeJourneyService(source)
        service = RecoveryIntelligenceService(fake, CONFIG)
        result = service.get("case-1")
        self.assertEqual(fake.calls, 1)
        self.assertEqual(result.decision.selected_action, "RETRY_LATER")
        self.assertEqual(result.decision.alternatives[0].action, "PAYMENT_LINK")
        self.assertEqual(result.intervention.provider_mode, "LOCAL")
        self.assertEqual(result.outcome.status, "PENDING")
        self.assertEqual(source["case"]["status"], "NEW")

    def test_decision_factors_and_constraints_are_copied_from_stored_trace(self) -> None:
        source = journey()
        source["decision"]["trace_json"].update({"fatigue_changed_winner": True, "constraint_changed_winner": True})
        result = RecoveryIntelligenceService(FakeJourneyService(source), CONFIG).get("case-1")
        self.assertTrue(result.decision.cost_affected)
        self.assertTrue(result.decision.fatigue_affected)
        self.assertTrue(result.decision.constraint_affected)
        self.assertEqual(result.decision.constraints[0].reason, "outside_contact_window")

    def test_recovered_and_unrecovered_statuses_use_persisted_outcomes(self) -> None:
        recovered = journey(status="RECOVERED")
        recovered["interventions"][0]["status"] = "RECOVERED"
        recovered["interventions"][0]["outcomes"] = [{"id": "outcome-1", "status": "RECOVERED", "recovered_amount_paise": 166508, "occurred_at": "2026-08-26T11:00:00+00:00"}]
        result = RecoveryIntelligenceService(FakeJourneyService(recovered), CONFIG).get("case-1")
        self.assertEqual(result.outcome.status, "RECOVERED")
        self.assertEqual(result.outcome.recovered_amount_paise, 166508)

        unrecovered = journey(status="UNRECOVERED")
        unrecovered["interventions"][0]["status"] = "FAILED"
        unrecovered["interventions"][0]["outcomes"] = [{"id": "outcome-2", "status": "NOT_RECOVERED", "recovered_amount_paise": None, "occurred_at": "2026-08-26T11:00:00+00:00"}]
        failed = RecoveryIntelligenceService(FakeJourneyService(unrecovered), CONFIG).get("case-1")
        self.assertEqual(failed.outcome.status, "NOT_RECOVERED")
        self.assertIsNone(failed.outcome.recovered_amount_paise)

    def test_voice_mode_requires_provider_evidence_for_live_language(self) -> None:
        source = journey()
        source["decision"]["selected_action"] = "VOICE_RECOVERY"
        source["interventions"][0].update({"action": "VOICE_RECOVERY", "status": "AWAITING_OUTCOME"})
        source["voice_calls"] = [{"status": "COMPLETED", "provider_mode": "LOCAL", "provider_call_reference": None, "outcome_intent": "REQUEST_PAYMENT_LINK", "events": [{"event_type": "PAYMENT_LINK_ATTACHED"}]}]
        result = RecoveryIntelligenceService(FakeJourneyService(source), CONFIG).get("case-1")
        self.assertEqual(result.intervention.voice.label, "Demo Voice Agent")
        self.assertTrue(result.intervention.voice.payment_link_requested)
        source["voice_calls"][0]["provider_mode"] = "LIVE"
        live_without_reference = RecoveryIntelligenceService(FakeJourneyService(source), CONFIG).get("case-1")
        self.assertEqual(live_without_reference.intervention.voice.label, "Demo Voice Agent")
        self.assertIn("no confirmed provider call reference", live_without_reference.intervention.voice.conversation_result)

    def test_response_schema_rejects_hidden_fields(self) -> None:
        result = RecoveryIntelligenceService(FakeJourneyService(journey()), CONFIG).get("case-1")
        payload = result.model_dump(mode="json")
        payload["hidden_state"] = {"segment": "NATURAL_PAYER"}
        with self.assertRaises(ValidationError):
            RecoveryIntelligenceResponse.model_validate(payload)

    def test_intelligence_endpoint_is_read_only_and_explicit(self) -> None:
        app = create_app("sqlite+pysqlite:///:memory:")
        session = app.state.session_factory()
        timestamp = datetime(2026, 8, 26, 10, tzinfo=timezone.utc)
        case = RecoveryCase(external_event_id="gate13-event", payment_id="gate13-payment", customer_id="synthetic-gate13", amount_paise=166508, currency="INR", failure_reason="technical_degradation", incident_flag=True, payment_method="card", decision_timestamp=timestamp, status="DECIDED")
        session.add(case)
        session.flush()
        decision = Decision(recovery_case_id=case.id, decision_run_id="gate13-run", selected_action="RETRY_LATER", predicted_probability=0.5, expected_gross_recovery_paise=83300, expected_net_value_paise=80000, model_version="test", feature_schema_version="test", engine_version="test", decision_timestamp=timestamp, trace_json={"highest_probability_action": "PAYMENT_LINK"})
        decision.candidates.append(DecisionCandidate(action="RETRY_LATER", status="PERMISSIBLE", predicted_probability=0.5, recoverable_amount_paise=166508, expected_gross_recovery_paise=83300, action_cost_paise=500, incentive_cost_paise=0, fatigue_penalty_paise=0, expected_net_value_paise=80000, expected_net_without_action_cost_paise=80500, expected_net_without_fatigue_paise=80000, rank=1, friction_rank=1, fatigue_reason="none"))
        session.add(decision)
        session.commit()
        case_id = case.id
        session.close()
        with patch("backend.app.services.case_service.CaseService.decide", side_effect=AssertionError("intelligence must not decide")):
            response = TestClient(app).get(f"/api/v1/recovery-cases/{case_id}/intelligence")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["diagnosis"]["primary_cause"], "TECHNICAL_INCIDENT")
        self.assertEqual(response.json()["decision"]["selected_action"], "RETRY_LATER")


if __name__ == "__main__":
    unittest.main()
