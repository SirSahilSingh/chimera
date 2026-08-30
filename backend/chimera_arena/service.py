"""Small API-facing adapter around the frozen Recovery Arena runner."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from backend.chimera_engine import ChimeraPolicyAdapter, DecisionEngine
from backend.chimera_model import BenchmarkProbabilityModel, Gate4ModelAdapter, build_feature_builder
from backend.chimera_engine.config import DecisionEngineConfig
from backend.chimera_simulator import ArenaRunner, Simulator, primary_baseline_policies
from backend.chimera_simulator.config import SimulatorConfig


class ArenaComparisonService:
    """Run the approved strategies against one shared synthetic event batch."""

    def __init__(self, simulator_config: SimulatorConfig, model_path: str | Path) -> None:
        self.simulator_config = simulator_config
        self.model_path = Path(model_path)

    def run(self, *, seeds: Iterable[int], count_per_seed: int) -> dict:
        simulator = Simulator(self.simulator_config.source_path)
        seed_list = list(seeds)
        batch = [
            case
            for seed in seed_list
            for case in simulator.generate_batch("arena_development", seed, count_per_seed)
        ]
        selected_model = BenchmarkProbabilityModel.load(
            self.model_path,
            expected_simulator_version=simulator.config.simulator_version,
            expected_config_hash=simulator.config.config_hash,
        )
        model = Gate4ModelAdapter(
            selected_model,
            build_feature_builder().schema,
            DecisionEngineConfig().compatible_model_version,
        )
        chimera = ChimeraPolicyAdapter(DecisionEngine(model, simulator.config))
        policies = (*primary_baseline_policies(), chimera)
        report = ArenaRunner(simulator.config).run(
            simulator,
            "arena_development",
            seed_list,
            count_per_seed,
            policies,
        )

        labels = {
            "RETRY_ALL": "Retry-All",
            "SIMPLE_RULE_BASED": "Rule Engine",
            "CHIMERA": "Chimera",
        }
        rows = []
        max_recovered = 0
        for policy_name in ("RETRY_ALL", "SIMPLE_RULE_BASED", "CHIMERA"):
            metrics = report.aggregate_results[policy_name]
            recovered_revenue = int(round(metrics["gross_recovered_value_paise"]["mean"]))
            net_value = int(round(metrics["net_recovery_value_paise"]["mean"]))
            action_counts = metrics["action_counts"]
            interventions = int(round(
                metrics["total_events"]["mean"] - action_counts["DO_NOTHING"]["mean"]
            ))
            policy_violations = int(round(metrics["policy_violations"]["mean"]))
            max_recovered = max(max_recovered, recovered_revenue)
            rows.append({
                "strategy": labels[policy_name],
                "policy_name": policy_name,
                "recovered_revenue_paise": recovered_revenue,
                "net_value_paise": net_value,
                "interventions": interventions,
                "policy_violations": policy_violations,
                "recovery_rate": metrics["recovery_rate"]["mean"],
            })
        for row in rows:
            row["bar_percent"] = round(
                row["recovered_revenue_paise"] / max_recovered * 100, 1
            ) if max_recovered else 0.0

        return {
            "batch": {
                "label": f"{report.metadata['total_events']} synthetic events",
                "total_events": report.metadata["total_events"],
                "value_at_risk_paise": int(round(
                    sum(case.event.amount_paise for case in batch)
                )),
                "seeds": report.metadata["seeds"],
                "count_per_seed": report.metadata["count_per_seed"],
            },
            "rows": rows,
            "methodology": "Same batch, same events, run through each strategy independently. Results are simulated, not production data.",
            "same_event_batch_across_policies": report.same_event_batch_across_policies,
            "simulator_version": report.metadata["simulator_version"],
            "config_hash": report.metadata["config_hash"],
        }
