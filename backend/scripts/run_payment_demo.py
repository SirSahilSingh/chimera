from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient
from backend.app.db.models import Decision, RecoveryCase
from backend.app.main import create_app
from backend.chimera_payments.schemas import PaymentDemoScenario


def make_intervention(app, action: str, suffix: str) -> str:
    session = app.state.session_factory()
    case = RecoveryCase(external_event_id=f"payment-demo-event-{suffix}", payment_id=f"payment-demo-{suffix}", customer_id=f"synthetic-demo-{suffix}", amount_paise=12500, currency="INR", failure_reason="issuer_decline", incident_flag=False, payment_method="card", decision_timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc), status="DECIDED")
    session.add(case)
    session.flush()
    decision = Decision(recovery_case_id=case.id, decision_run_id=f"payment-demo-run-{suffix}", selected_action=action, predicted_probability=0.5, expected_gross_recovery_paise=6250, expected_net_value_paise=5000, model_version="demo", feature_schema_version="demo", engine_version="demo", decision_timestamp=case.decision_timestamp, trace_json={})
    session.add(decision)
    session.commit()
    client = TestClient(app)
    intervention = client.post(f"/api/v1/decisions/{decision.id}/interventions").json()
    client.post(f"/api/v1/interventions/{intervention['id']}/queue")
    session.close()
    return intervention["id"]


def main() -> None:
    app = create_app("sqlite+pysqlite:///:memory:")
    client = TestClient(app)
    for action, scenario, label in (("PAYMENT_LINK", PaymentDemoScenario.PAYMENT_SUCCESS, "direct success"), ("VOICE_RECOVERY", PaymentDemoScenario.PAYMENT_SUCCESS, "voice-requested link"), ("PAYMENT_LINK", PaymentDemoScenario.PAYMENT_EXPIRED, "expired link")):
        intervention_id = make_intervention(app, action, label.replace(" ", "-"))
        if action == "VOICE_RECOVERY":
            call = client.post(f"/api/v1/interventions/{intervention_id}/voice/demo", json={"scenario": "customer_requests_payment_link"}).json()
            session = app.state.session_factory()
            from backend.app.db.models import PaymentLink
            link = session.query(PaymentLink).filter_by(intervention_id=intervention_id).one()
            payment_id = link.id
            session.close()
        else:
            link = client.post(f"/api/v1/interventions/{intervention_id}/payment-link").json()
            payment_id = link["id"]
        result = client.post(f"/api/v1/payments/{payment_id}/demo/complete", json={"scenario": scenario.value}).json()
        intervention = client.get(f"/api/v1/interventions/{intervention_id}").json()
        print(f"{label}: payment={result['status']} intervention={intervention['status']} url={link['short_url'] if isinstance(link, dict) else link.short_url}")


if __name__ == "__main__":
    main()
