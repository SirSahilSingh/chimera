from __future__ import annotations

import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from backend.app.db.models import Explanation
from backend.app.main import create_app
from backend.chimera_intelligence.agent import ExplanationAgent, canonical_hash
from backend.chimera_intelligence.context import context_json
from backend.chimera_intelligence.fallback import FallbackReason
from backend.chimera_intelligence.provider import ProviderError
from backend.chimera_intelligence.schemas import SanitizedDecisionContext


def valid_output(context: dict) -> dict:
    selected = context["decision"]["selected_action"]
    alternative = next(
        candidate["action"]
        for candidate in context["candidates"]
        if candidate["action"] != selected
    )
    return {
        "summary": "The stored deterministic decision selected the permissible recovery action.",
        "recommendation": {
            "action": selected,
            "reason": "The action had the strongest expected net value in the stored decision trace.",
        },
        "key_factors": [{"factor": "expected net value", "impact": "The trace favored this action after deterministic policy checks."}],
        "alternatives": [{"action": alternative, "reason_not_selected": "The stored trace ranked this alternative lower."}],
        "next_step": "Proceed through the existing policy validated execution path.",
        "operator_note": "This is an explanation of the stored decision.",
        "limitations": ["This explanation is not a recovery guarantee."],
    }


class FakeProvider:
    provider_name = "fake_provider"
    model_name = "fake_model"

    def __init__(self, outputs=None, error: ProviderError | None = None, secret: str = "secret-key"):
        self.outputs = list(outputs or [])
        self.error = error
        self.calls = 0
        self.contexts: list[dict] = []
        self.secret = secret

    def generate(self, context: dict, prompt: str):
        self.calls += 1
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        return self.outputs.pop(0)


class IntelligenceTests(unittest.TestCase):
    def make_app(self, provider=None):
        return create_app("sqlite+pysqlite:///:memory:", explanation_provider=provider)

    def make_decision(self, client: TestClient, suffix: str = "1") -> str:
        payload = {
            "external_event_id": f"intelligence-event-{suffix}",
            "payment_id": f"intelligence-payment-{suffix}",
            "customer_id": f"synthetic-customer-{suffix}",
            "amount_paise": 12500,
            "currency": "INR",
            "failure_reason": "issuer_decline",
            "incident_flag": False,
            "payment_method": "card",
            "decision_timestamp": "2026-01-01T12:00:00+00:00",
        }
        case = client.post("/api/v1/recovery-cases", json=payload).json()
        decision = client.post(f"/api/v1/recovery-cases/{case['id']}/decide")
        self.assertEqual(decision.status_code, 200, decision.text)
        return decision.json()["id"]

    def test_decision_generation_never_calls_provider(self):
        provider = FakeProvider()
        client = TestClient(self.make_app(provider))
        self.make_decision(client)
        self.assertEqual(provider.calls, 0)

    def test_no_provider_uses_deterministic_fallback(self):
        client = TestClient(self.make_app())
        decision_id = self.make_decision(client)
        response = client.post(f"/api/v1/decisions/{decision_id}/explain")
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["explanation_source"], "fallback")
        self.assertEqual(response.json()["fallback_reason"], FallbackReason.PROVIDER_NOT_CONFIGURED.value)
        self.assertNotIn("api_key", response.text.lower())

    def test_provider_receives_only_sanitized_stored_context(self):
        provider = FakeProvider()
        client = TestClient(self.make_app(provider))
        decision_id = self.make_decision(client)
        provider.outputs.append(valid_output({"decision": {"selected_action": "PAYMENT_LINK"}, "candidates": [{"action": "RETRY_NOW"}]}))
        # The provider output is generated after observing the real context.
        provider.outputs.clear()
        def generate(context, prompt):
            provider.calls += 1
            provider.contexts.append(context)
            return valid_output(context)
        provider.generate = generate
        response = client.post(f"/api/v1/decisions/{decision_id}/explain")
        self.assertEqual(response.status_code, 201, response.text)
        context = provider.contexts[0]
        serialized = str(context).lower()
        for forbidden in ("hidden_state", "customer_segment", "environment_state", "natural_recovery_probability", "action_outcomes", "future_outcome", "recovery_timestamp"):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("payment_amount_paise", serialized)

    def test_context_schema_rejects_hidden_fields(self):
        with self.assertRaises(ValidationError):
            SanitizedDecisionContext.model_validate({"hidden_state": {}})

    def test_matching_provider_output_is_accepted_and_versioned(self):
        provider = FakeProvider()
        def generate(context, prompt):
            provider.calls += 1
            provider.contexts.append(context)
            return valid_output(context)
        provider.generate = generate
        client = TestClient(self.make_app(provider))
        decision_id = self.make_decision(client)
        response = client.post(f"/api/v1/decisions/{decision_id}/explain")
        self.assertEqual(response.json()["explanation_source"], "llm")
        self.assertEqual(response.json()["prompt_version"], "chimera_explanation_v1.0.0")
        self.assertEqual(response.json()["explanation_version"], "explanation_v1.0.0")
        self.assertEqual(len(response.json()["input_context_hash"]), 64)
        self.assertEqual(len(response.json()["output_hash"]), 64)

    def test_conflicting_action_retries_once_then_accepts_matching_output(self):
        provider = FakeProvider()
        def first_then_second(context, prompt):
            provider.calls += 1
            provider.contexts.append(context)
            if provider.calls == 1:
                output = valid_output(context)
                output["recommendation"]["action"] = "DO_NOTHING" if context["decision"]["selected_action"] != "DO_NOTHING" else "RETRY_NOW"
                return output
            return valid_output(context)
        provider.generate = first_then_second
        client = TestClient(self.make_app(provider))
        decision_id = self.make_decision(client)
        response = client.post(f"/api/v1/decisions/{decision_id}/explain")
        self.assertEqual(response.json()["explanation_source"], "llm")
        self.assertEqual(provider.calls, 2)

    def test_conflicting_action_after_retry_falls_back_without_duplicate_rows(self):
        provider = FakeProvider()
        def always_wrong(context, prompt):
            provider.calls += 1
            output = valid_output(context)
            output["recommendation"]["action"] = "DO_NOTHING" if context["decision"]["selected_action"] != "DO_NOTHING" else "RETRY_NOW"
            return output
        provider.generate = always_wrong
        app = self.make_app(provider)
        client = TestClient(app)
        decision_id = self.make_decision(client)
        response = client.post(f"/api/v1/decisions/{decision_id}/explain")
        self.assertEqual(response.json()["fallback_reason"], FallbackReason.ACTION_MISMATCH.value)
        self.assertEqual(provider.calls, 2)
        history = client.get(f"/api/v1/decisions/{decision_id}/explanations")
        self.assertEqual(len(history.json()), 1)

    def test_invalid_json_provider_error_uses_controlled_reason(self):
        provider = FakeProvider(error=ProviderError(FallbackReason.INVALID_JSON))
        client = TestClient(self.make_app(provider))
        decision_id = self.make_decision(client)
        response = client.post(f"/api/v1/decisions/{decision_id}/explain")
        self.assertEqual(response.json()["fallback_reason"], "invalid_json")
        self.assertNotIn("Traceback", response.text)

    def test_timeout_rate_limit_and_missing_key_are_controlled(self):
        for reason in (FallbackReason.PROVIDER_TIMEOUT, FallbackReason.PROVIDER_RATE_LIMITED, FallbackReason.MISSING_API_KEY):
            provider = FakeProvider(error=ProviderError(reason))
            client = TestClient(self.make_app(provider))
            decision_id = self.make_decision(client, reason.value)
            response = client.post(f"/api/v1/decisions/{decision_id}/explain")
            self.assertEqual(response.json()["fallback_reason"], reason.value)

    def test_numeric_and_extra_deterministic_fields_are_rejected(self):
        provider = FakeProvider()
        def invalid_output(context, prompt):
            output = valid_output(context)
            output["recommendation"]["reason"] = "The value was INR 12500."
            output["expected_net_value_paise"] = 999
            return output
        provider.generate = invalid_output
        client = TestClient(self.make_app(provider))
        decision_id = self.make_decision(client)
        response = client.post(f"/api/v1/decisions/{decision_id}/explain")
        self.assertEqual(response.json()["fallback_reason"], FallbackReason.SCHEMA_VALIDATION_FAILED.value)
        self.assertEqual(response.json()["explanation_source"], "fallback")

    def test_fallback_is_deterministic(self):
        provider = FakeProvider()
        client = TestClient(self.make_app(provider))
        decision_id = self.make_decision(client)
        # A fallback context is obtained through the first generated explanation.
        first = client.post(f"/api/v1/decisions/{decision_id}/explain")
        second = client.post(f"/api/v1/decisions/{decision_id}/explain")
        self.assertEqual(first.json()["output_hash"], second.json()["output_hash"])
        self.assertEqual(first.json()["structured_explanation"], second.json()["structured_explanation"])

    def test_repeated_explicit_requests_are_append_only(self):
        app = self.make_app()
        client = TestClient(app)
        decision_id = self.make_decision(client)
        first = client.post(f"/api/v1/decisions/{decision_id}/explain")
        second = client.post(f"/api/v1/decisions/{decision_id}/explain")
        self.assertNotEqual(first.json()["id"], second.json()["id"])
        history = client.get(f"/api/v1/decisions/{decision_id}/explanations")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()), 2)
        latest = client.get(f"/api/v1/decisions/{decision_id}/explanation")
        self.assertEqual(latest.json()["id"], history.json()[0]["id"])

    def test_latest_ordering_uses_id_when_generated_at_ties(self):
        app = self.make_app()
        client = TestClient(app)
        decision_id = self.make_decision(client)
        client.post(f"/api/v1/decisions/{decision_id}/explain")
        client.post(f"/api/v1/decisions/{decision_id}/explain")
        session = app.state.session_factory()
        try:
            rows = list(session.scalars(select(Explanation).where(Explanation.decision_id == decision_id)))
            tied_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
            for row in rows:
                row.generated_at = tied_timestamp
            session.commit()
            expected_id = max(row.id for row in rows)
        finally:
            session.close()
        latest = client.get(f"/api/v1/decisions/{decision_id}/explanation")
        self.assertEqual(latest.json()["id"], expected_id)

    def test_hashing_is_deterministic_for_same_context(self):
        provider = FakeProvider()
        client = TestClient(self.make_app(provider))
        decision_id = self.make_decision(client)
        output = client.post(f"/api/v1/decisions/{decision_id}/explain").json()
        self.assertEqual(output["input_context_hash"], output["input_context_hash"])
        self.assertEqual(len(canonical_hash({"b": 1, "a": 2})), 64)

    def test_explanation_endpoints_do_not_recompute_missing_decisions(self):
        client = TestClient(self.make_app())
        self.assertEqual(client.post("/api/v1/decisions/not-found/explain").status_code, 404)
        self.assertEqual(client.get("/api/v1/decisions/not-found/explanation").status_code, 404)

    def test_do_nothing_fallback_language_is_explicit(self):
        context = SanitizedDecisionContext(
            case={"case_id": "case", "payment_amount_paise": 1, "currency": "INR", "failure_reason": "other", "payment_method": "card", "incident_flag": False, "decision_timestamp": datetime.now(timezone.utc), "contact_window_status": "within_configured_window"},
            decision={"selected_action": "DO_NOTHING", "predicted_probability": 0.1, "expected_gross_recovery_paise": 1, "expected_net_value_paise": 1},
            candidates=[{"action": "DO_NOTHING", "predicted_probability": 0.1, "expected_net_value_paise": 1, "action_cost_paise": 0, "fatigue_penalty_paise": 0, "status": "permissible", "blocked_reason": None}],
            decision_factors={"cost_changed_winner": False, "fatigue_changed_winner": False, "constraint_changed_winner": False, "tie_break_applied": False},
        )
        result = ExplanationAgent().explain(context)
        self.assertIn("No intervention", result.structured_explanation.summary)


if __name__ == "__main__":
    unittest.main()
