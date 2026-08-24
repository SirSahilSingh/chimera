#!/usr/bin/env python3
"""Generate a synthetic batch, truth artifact, and diagnostics report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.chimera_simulator import Simulator, SimulatorConfig  # noqa: E402
from backend.chimera_simulator.diagnostics import build_diagnostics  # noqa: E402
from backend.chimera_simulator.serialization import event_to_jsonable, truth_to_jsonable  # noqa: E402


def _write_json_lines(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPOSITORY_ROOT / "backend/configs/simulator_v1.yaml")
    parser.add_argument("--split", default="arena_development")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--events-output", type=Path)
    parser.add_argument("--truth-output", type=Path)
    parser.add_argument("--diagnostics-output", type=Path)
    args = parser.parse_args()

    config = SimulatorConfig.from_file(args.config)
    simulator = Simulator(config)
    cases = simulator.generate_batch(args.split, args.seed, args.count)
    diagnostics = build_diagnostics(cases)
    if args.events_output:
        _write_json_lines(args.events_output, [event_to_jsonable(case.event) for case in cases])
    if args.truth_output:
        _write_json_lines(args.truth_output, [truth_to_jsonable(case) for case in cases])
    if args.diagnostics_output:
        args.diagnostics_output.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostics_output.write_text(
            json.dumps(diagnostics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"config_hash": config.config_hash, **diagnostics}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
