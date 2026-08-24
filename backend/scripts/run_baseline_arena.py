"""Run the Gate 2 baseline policies on a development Arena batch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.chimera_simulator import ArenaRunner, Simulator, primary_baseline_policies


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "backend" / "configs" / "simulator_v1.yaml")
    parser.add_argument("--split", default="arena_development")
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--count-per-seed", type=int, default=1000)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "simulator_v1" / "baseline_arena_dev.json",
    )
    args = parser.parse_args()

    simulator = Simulator(args.config)
    report = ArenaRunner(simulator.config).run(
        simulator=simulator,
        split=args.split,
        seeds=args.seeds,
        count_per_seed=args.count_per_seed,
        policies=primary_baseline_policies(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **report.metadata}, indent=2, sort_keys=True))
    print(json.dumps({"aggregate_results": report.aggregate_results}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
