from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable


def transcript_hash(turns: Iterable) -> str:
    rows = []
    for turn in sorted(turns, key=lambda item: (item.sequence_number, item.id)):
        rows.append({
            "sequence_number": turn.sequence_number,
            "speaker": turn.speaker,
            "text": turn.text,
            "intent": turn.intent,
            "confidence": turn.confidence,
            "requested_action": turn.requested_action,
            "requires_confirmation": turn.requires_confirmation,
            "timestamp": turn.timestamp.isoformat(),
            "validated": turn.validated,
        })
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
