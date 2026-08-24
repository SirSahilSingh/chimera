#!/usr/bin/env python3
"""Run cross-tab diagnostics over multiple development seeds."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPOSITORY_ROOT / "backend/configs/simulator_v1.yaml")
    parser.add_argument("--split", default="arena_development")
    parser.add_argument("--seeds", type=int, nargs="+", default=[400000, 410000, 420000, 430000, 440000])
    parser.add_argument("--count-per-seed", type=int, default=1000)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "data/simulator_v1/dev_diagnostics_5000.json",
    )
    args = parser.parse_args()

    config = SimulatorConfig.from_file(args.config)
    simulator = Simulator(config)
    cases = []
    for seed in args.seeds:
        cases.extend(simulator.generate_batch(args.split, seed, args.count_per_seed))
    diagnostics = build_diagnostics(cases)
    diagnostics["batch_metadata"] = {
        "split": args.split,
        "seeds": args.seeds,
        "count_per_seed": args.count_per_seed,
        "config_hash": config.config_hash,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
