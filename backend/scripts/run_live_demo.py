"""Run a local Gate 11 recovery journey using only synthetic observable input."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.main import create_app


def main() -> None:
    app = create_app("sqlite+pysqlite:///:memory:")
    payload = {
        "external_event_id": "gate11-demo-expired-method-001",
        "payment_id": "demo_payment_001",
        "customer_id": "demo_customer_001",
        "amount_paise": 129900,
        "currency": "INR",
        "failure_reason": "expired_method",
        "incident_flag": False,
        "payment_method": "card",
        "decision_timestamp": datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc).isoformat(),
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/demo/recovery", json=payload)
        response.raise_for_status()
        result = response.json()
        print("Gate 11 provider mode:", result.get("provider_mode") or "NONE")
        print("Selected action:", result["selected_action"])
        print("Case:", result["case_id"])
        print("Decision:", result["decision_id"])
        print("Intervention:", result["intervention_id"])
        if result["selected_action"] == "PAYMENT_LINK":
            journey_before = client.get(result["journey_url"])
            journey_before.raise_for_status()
            payments = journey_before.json()["payments"]
            if payments:
                completed = client.post(f"/api/v1/payments/{payments[0]['id']}/demo/complete", json={"scenario": "payment_success"})
                completed.raise_for_status()
                print("Local payment outcome:", completed.json()["status"])
        journey = client.get(result["journey_url"])
        journey.raise_for_status()
        print("Journey events:", len(journey.json()["audit_trail"]))


if __name__ == "__main__":
    main()
