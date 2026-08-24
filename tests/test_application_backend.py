from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.domain import CaseStatus, DomainError, transition
from backend.app.main import create_app
from backend.app.db.models import ActionExecution, AuditLog
from backend.chimera_simulator.models import ACTIONS


class ApplicationBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("sqlite+pysqlite:///:memory:")
        self.client = TestClient(self.app)

    def payload(self, suffix: str = "1") -> dict:
        return {
            "external_event_id": f"evt-{suffix}",
            "payment_id": f"pay-{suffix}",
            "customer_id": f"cust-{suffix}",
            "amount_paise": 12500,
            "currency": "INR",
            "failure_reason": "issuer_decline",
            "incident_flag": False,
            "payment_method": "card",
            "decision_timestamp": "2026-01-01T12:00:00+00:00",
        }

    def test_create_case_uses_integer_paise_and_rejects_float(self) -> None:
        response = self.client.post("/api/v1/recovery-cases", json=self.payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["amount_paise"], 12500)
        invalid = self.payload("float")
        invalid["amount_paise"] = 125.0
        self.assertEqual(self.client.post("/api/v1/recovery-cases", json=invalid).status_code, 422)

    def test_currency_and_hidden_fields_are_rejected(self) -> None:
        invalid = self.payload("hidden")
        invalid["currency"] = "USD"
        self.assertEqual(self.client.post("/api/v1/recovery-cases", json=invalid).status_code, 422)
        hidden = self.payload("extra")
        hidden["customer_segment"] = "NATURAL_PAYER"
        self.assertEqual(self.client.post("/api/v1/recovery-cases", json=hidden).status_code, 422)

    def test_duplicate_external_event_is_rejected(self) -> None:
        self.assertEqual(self.client.post("/api/v1/recovery-cases", json=self.payload()).status_code, 201)
        self.assertEqual(self.client.post("/api/v1/recovery-cases", json=self.payload()).status_code, 409)

    def test_decision_persists_full_candidate_trace_and_uses_selected_model(self) -> None:
        created = self.client.post("/api/v1/recovery-cases", json=self.payload()).json()
        response = self.client.post(f"/api/v1/recovery-cases/{created['id']}/decide")
        self.assertEqual(response.status_code, 200, response.text)
        decision = response.json()
        self.assertEqual(decision["model_version"], "recovery_model_v2_interaction_lr.0.0")
        self.assertEqual(decision["feature_schema_version"], "features_v2.0.0_interaction")
        self.assertEqual(len(decision["candidates"]), len(ACTIONS))
        self.assertEqual(self.client.get(f"/api/v1/decisions/{decision['id']}").status_code, 200)

    def test_execute_is_deterministically_idempotent(self) -> None:
        created = self.client.post("/api/v1/recovery-cases", json=self.payload()).json()
        self.client.post(f"/api/v1/recovery-cases/{created['id']}/decide")
        first = self.client.post(f"/api/v1/recovery-cases/{created['id']}/execute")
        second = self.client.post(f"/api/v1/recovery-cases/{created['id']}/execute")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(first.json()["idempotency_key"], second.json()["idempotency_key"])
        with self.app.state.engine.connect() as connection:
            pass

    def test_execute_requires_decision(self) -> None:
        created = self.client.post("/api/v1/recovery-cases", json=self.payload()).json()
        self.assertEqual(self.client.post(f"/api/v1/recovery-cases/{created['id']}/execute").status_code, 409)

    def test_state_machine_rejects_invalid_transition(self) -> None:
        with self.assertRaises(DomainError):
            transition(CaseStatus.NEW.value, CaseStatus.ACTION_EXECUTED)
        with self.assertRaises(DomainError):
            transition(CaseStatus.CLOSED.value, CaseStatus.NEW)

    def test_list_paginates_and_filters(self) -> None:
        self.client.post("/api/v1/recovery-cases", json=self.payload("a"))
        other = self.payload("b")
        other["failure_reason"] = "expired_method"
        self.client.post("/api/v1/recovery-cases", json=other)
        response = self.client.get("/api/v1/recovery-cases", params={"page": 1, "page_size": 1, "failure_reason": "expired_method"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(len(response.json()["items"]), 1)

    def test_case_detail_contains_audit_summary(self) -> None:
        created = self.client.post("/api/v1/recovery-cases", json=self.payload()).json()
        detail = self.client.get(f"/api/v1/recovery-cases/{created['id']}").json()
        self.assertEqual(detail["audit_count"], 1)

    def test_health_reports_model_compatibility(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model_compatibility"], "compatible")

    def test_only_observable_case_contract_is_accepted(self) -> None:
        payload = self.payload("observable")
        for forbidden in ("hidden_state", "environment_state", "natural_recovery_probability", "action_outcomes", "recovered"):
            candidate = dict(payload)
            candidate[forbidden] = "forbidden"
            self.assertEqual(self.client.post("/api/v1/recovery-cases", json=candidate).status_code, 422)

    def test_missing_case_is_not_found(self) -> None:
        self.assertEqual(self.client.get("/api/v1/recovery-cases/not-found").status_code, 404)
        self.assertEqual(self.client.post("/api/v1/recovery-cases/not-found/decide").status_code, 404)


if __name__ == "__main__":
    unittest.main()
