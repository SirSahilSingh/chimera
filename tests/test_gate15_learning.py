from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.models import Decision
from backend.app.main import create_app
from backend.chimera_learning.aggregation import actions
from backend.chimera_learning.calibration import calibration_report
from backend.chimera_learning.validation import validate_learning_payload
from backend.chimera_simulator.models import ACTIONS


class Gate15LearningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app("sqlite+pysqlite:///:memory:")
        self.client = TestClient(self.app)
        for scenario in ("payment_recovery", "technical_retry", "voice_recovery", "escalation"):
            response = self.client.post("/api/v1/demo/run", json={"scenario": scenario, "provider_mode": "LOCAL"})
            self.assertEqual(response.status_code, 201, response.text)

    def test_action_report_includes_all_seven_actions(self) -> None:
        response = self.client.get("/api/v1/learning/actions")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([row["action"] for row in response.json()["actions"]], list(ACTIONS))

    def test_overview_is_observational_and_mode_separated(self) -> None:
        response = self.client.get("/api/v1/learning/overview?provider_mode=LOCAL")
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["provider_modes"], ["LOCAL"])
        self.assertEqual(body["data_warning"], "Demo / non-production outcome data")
        self.assertIn("calibration", body)
        self.assertIn("failures", body)

    def test_calibration_gap_and_brier_score_are_deterministic(self) -> None:
        result = calibration_report([(0.75, True), (0.25, False)])
        self.assertAlmostEqual(result["calibration_gap"], 0.0)
        self.assertAlmostEqual(result["brier_score"], 0.0625)

    def test_learning_payload_rejects_hidden_truth(self) -> None:
        with self.assertRaises(ValueError):
            validate_learning_payload({"environment_state": "NORMAL"})

    def test_learning_reports_are_append_only_and_do_not_mutate_decisions(self) -> None:
        session = self.app.state.session_factory()
        before = {row.id: row.selected_action for row in session.scalars(select(Decision))}
        session.close()
        first = self.client.post("/api/v1/learning/reports", json={"report_type": "overview"})
        second = self.client.post("/api/v1/learning/reports", json={"report_type": "overview"})
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertNotEqual(first.json()["id"], second.json()["id"])
        reports = self.client.get("/api/v1/learning/reports")
        self.assertEqual(len(reports.json()), 2)
        session = self.app.state.session_factory()
        after = {row.id: row.selected_action for row in session.scalars(select(Decision))}
        session.close()
        self.assertEqual(before, after)

    def test_drift_reports_insufficient_data_without_fabricating_findings(self) -> None:
        response = self.client.get("/api/v1/learning/drift")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "INSUFFICIENT_DATA")
        self.assertEqual(response.json()["metrics"], [])


if __name__ == "__main__":
    unittest.main()
