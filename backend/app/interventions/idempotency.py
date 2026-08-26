from __future__ import annotations

import hashlib


def intervention_idempotency_key(*, decision_id: str, decision_run_id: str, action: str) -> str:
    material = f"chimera-intervention-v1|{decision_id}|{decision_run_id}|{action}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def execution_idempotency_key(*, intervention_id: str, attempt_number: int, action: str) -> str:
    material = f"chimera-execution-v1|{intervention_id}|{attempt_number}|{action}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
