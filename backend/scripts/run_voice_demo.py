from __future__ import annotations

import itertools
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.main import create_app


SCENARIOS = (
    "customer_agrees_to_pay",
    "customer_requests_payment_link",
    "customer_declines",
)


def find_voice_decision(client: TestClient, serial: int) -> dict:
    reasons = ("issuer_decline", "expired_method", "technical_degradation", "insufficient_funds", "abandonment", "other")
    methods = ("card", "upi", "netbanking")
    amounts = (100, 500, 1000, 5000, 12500, 50000, 100000)
    for index, (amount, reason, incident_flag, method) in enumerate(itertools.product(amounts, reasons, (False, True), methods)):
        suffix = f"voice-demo-{serial}-{index}"
        case = client.post(
            "/api/v1/recovery-cases",
            json={
                "external_event_id": f"evt-{suffix}",
                "payment_id": f"pay-{suffix}",
                "customer_id": f"synthetic-{suffix}",
                "amount_paise": amount,
                "currency": "INR",
                "failure_reason": reason,
                "incident_flag": incident_flag,
                "payment_method": method,
                "decision_timestamp": "2026-01-01T12:00:00+00:00",
            },
        )
        case.raise_for_status()
        decision = client.post(f"/api/v1/recovery-cases/{case.json()['id']}/decide")
        decision.raise_for_status()
        value = decision.json()
        if value["selected_action"] == "VOICE_RECOVERY":
            return value
    raise RuntimeError("the frozen decision model did not select VOICE_RECOVERY in the demo search space")


def main() -> None:
    app = create_app("sqlite+pysqlite:///:memory:")
    with TestClient(app) as client:
        print("CHIMERA Gate 8 — local voice recovery demo")
        print("Provider: local deterministic (no credentials)\n")
        for serial, scenario in enumerate(SCENARIOS, start=1):
            decision = find_voice_decision(client, serial)
            intervention = client.post(f"/api/v1/decisions/{decision['id']}/interventions")
            intervention.raise_for_status()
            queued = client.post(f"/api/v1/interventions/{intervention.json()['id']}/queue")
            queued.raise_for_status()
            call = client.post(
                f"/api/v1/interventions/{intervention.json()['id']}/voice/demo",
                json={"scenario": scenario},
            )
            call.raise_for_status()
            result = call.json()
            print(f"Scenario: {scenario}")
            print(f"  selected action: {decision['selected_action']}")
            print(f"  call lifecycle: {result['status']}")
            print(f"  captured intent: {result['outcome_intent']}")
            print(f"  intervention remains operationally separate: {result['intervention_id']}")
            print(f"  payment link: {result['payment_link'] or 'not requested'}")
            print(f"  transcript hash: {result['transcript_hash']}")
            print(f"  audit events: {', '.join(event['event_type'] for event in result['events'])}\n")


if __name__ == "__main__":
    main()
