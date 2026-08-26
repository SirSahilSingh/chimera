from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient
from backend.app.db.models import Decision, RecoveryCase
from backend.app.main import create_app


def make_intervention(client: TestClient, app, action: str, reason: str, suffix: str) -> str:
    session = app.state.session_factory()
    case = RecoveryCase(external_event_id=f"orchestration-demo-{suffix}", payment_id=f"orchestration-payment-{suffix}", customer_id=f"synthetic-orchestration-{suffix}", amount_paise=12500, currency="INR", failure_reason=reason, incident_flag=False, payment_method="card", decision_timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc), status="DECIDED")
    session.add(case)
    session.flush()
    decision = Decision(recovery_case_id=case.id, decision_run_id=f"orchestration-run-{suffix}", selected_action=action, predicted_probability=0.5, expected_gross_recovery_paise=6250, expected_net_value_paise=5000, model_version="demo", feature_schema_version="demo", engine_version="demo", decision_timestamp=case.decision_timestamp, trace_json={})
    session.add(decision)
    session.commit()
    decision_id = decision.id
    session.close()
    intervention = client.post(f"/api/v1/decisions/{decision_id}/interventions").json()
    client.post(f"/api/v1/interventions/{intervention['id']}/queue")
    return intervention["id"]


def main() -> None:
    app = create_app("sqlite+pysqlite:///:memory:")
    client = TestClient(app)
    cases = (("RETRY_LATER", "technical_degradation", "technical failure"), ("SEND_MESSAGE", "expired_method", "expired payment method"), ("RETRY_LATER", "insufficient_funds", "insufficient funds"), ("ESCALATE", "issuer_decline", "escalation"), ("DO_NOTHING", "other", "do nothing"))
    for action, reason, label in cases:
        intervention_id = make_intervention(client, app, action, reason, label.replace(" ", "-"))
        result = client.post(f"/api/v1/interventions/{intervention_id}/orchestrate")
        payload = result.json()
        if action == "RETRY_LATER" and result.status_code == 200 and payload.get("execution_status") == "SCHEDULED":
            result = client.post(f"/api/v1/retries/{payload['id']}/execute")
            payload = result.json()
            client.post(f"/api/v1/interventions/{intervention_id}/outcome", json={"status": "PENDING", "occurred_at": "2026-01-02T12:00:00+00:00", "source": "retry_provider"})
        print(f"{label}: action={action} status={result.status_code} operation_status={payload.get('execution_status', payload.get('delivery_state', payload.get('status')))}")


if __name__ == "__main__":
    main()
