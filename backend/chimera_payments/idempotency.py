from __future__ import annotations

import hashlib


def payment_idempotency_key(intervention_id: str, decision_id: str, provider: str) -> str:
    return hashlib.sha256(f"chimera-payment-link-v1|{intervention_id}|{decision_id}|{provider}".encode()).hexdigest()


def sha256_json(value: object) -> str:
    import json
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
