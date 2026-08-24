"""Evaluate CHIMERA against the approved Gate 2 baselines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.chimera_engine import ChimeraPolicyAdapter, DecisionEngine
from backend.chimera_engine.diagnostics import summarize_decisions
from backend.chimera_model import RecoveryProbabilityModel, build_feature_builder
from backend.chimera_simulator import ArenaRunner, Simulator, primary_baseline_policies


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "backend" / "configs" / "simulator_v1.yaml")
    parser.add_argument("--model", type=Path, default=ROOT / "data" / "model_v1" / "recovery_model_v1.json")
    parser.add_argument("--split", default="arena_development")
    parser.add_argument("--seeds", type=int, nargs="+", default=[400000, 410000, 420000, 430000, 440000])
    parser.add_argument("--count-per-seed", type=int, default=1000)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data" / "model_v1" / "gate4_arena_report.json"
    )
    args = parser.parse_args()

    simulator = Simulator(args.config)
    feature_builder = build_feature_builder()
    model = RecoveryProbabilityModel.load(
        args.model,
        expected_simulator_version=simulator.config.simulator_version,
        expected_config_hash=simulator.config.config_hash,
        expected_schema=feature_builder.schema,
    )
    engine = DecisionEngine(model, simulator.config)
    chimera = ChimeraPolicyAdapter(engine)
    policies = (*primary_baseline_policies(), chimera)
    report = ArenaRunner(simulator.config).run(
        simulator,
        args.split,
        args.seeds,
        args.count_per_seed,
        policies,
    )
    payload = report.to_dict()
    payload["chimera_decision_diagnostics"] = summarize_decisions(chimera.decisions.values())
    payload["chimera_sample_decision"] = next(
        (decision.to_dict() for decision in chimera.decisions.values()), None
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "metadata": report.metadata,
        "aggregate_results": report.aggregate_results,
        "chimera_decision_diagnostics": payload["chimera_decision_diagnostics"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
