"""JSON-safe serialization for decision-facing and simulator-truth artifacts."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any


def to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_jsonable(item) for item in value]
    return value


def event_to_jsonable(event: Any) -> dict[str, Any]:
    return to_jsonable(event)


def truth_to_jsonable(case: Any) -> dict[str, Any]:
    return to_jsonable(case)
