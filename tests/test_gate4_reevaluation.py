from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from backend.chimera_engine import ChimeraPolicyAdapter, DecisionEngine, DecisionEngineCompatibilityError
from backend.chimera_model import (
    BenchmarkProbabilityModel,
    Gate4ModelAdapter,
    INTERACTION_FEATURE_SCHEMA_VERSION,
    build_feature_builder,
)
from backend.chimera_simulator import Simulator, SimulatorConfig


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "backend" / "configs" / "simulator_v1.yaml"
V1_PATH = ROOT / "data" / "model_v1" / "recovery_model_v1.json"
V2_PATH = ROOT / "data" / "model_benchmark_v1" / "recovery_model_v2_interaction_lr.json"
V1_SHA256 = "a6a8de47d3bad06141ea5d418b6250bc8bd084ca9ee424e0bf74b6396ec2bdb4"


class Gate4ReevaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = SimulatorConfig.from_file(CONFIG_PATH)
        cls.simulator = Simulator(cls.config)
        cls.model = BenchmarkProbabilityModel.load(
            V2_PATH,
            expected_simulator_version=cls.config.simulator_version,
            expected_config_hash=cls.config.config_hash,
        )

    def _adapter(self) -> ChimeraPolicyAdapter:
        adapter = Gate4ModelAdapter(self.model, build_feature_builder().schema, "recovery_model_v1.0.0")
        return ChimeraPolicyAdapter(DecisionEngine(adapter, self.config))

    def test_selected_v2_model_loads_with_exact_schema_and_adapter(self) -> None:
        self.assertEqual(self.model.model_version, "recovery_model_v2_interaction_lr.0.0")
        self.assertEqual(self.model.feature_schema.version, INTERACTION_FEATURE_SCHEMA_VERSION)
        adapter = self._adapter()
        self.assertEqual(adapter.engine.model.selected_model.model_version, self.model.model_version)

    def test_v2_is_not_silently_accepted_without_explicit_adapter(self) -> None:
        with self.assertRaises(DecisionEngineCompatibilityError):
            DecisionEngine(self.model, self.config)

    def test_repeated_v2_decision_is_deterministic(self) -> None:
        event = self.simulator.generate_case("arena_development", 400000, 42).event
        first = self._adapter().engine.decide(event).to_dict()
        second = self._adapter().engine.decide(event).to_dict()
        self.assertEqual(first, second)

    def test_v1_artifact_remains_unchanged(self) -> None:
        self.assertEqual(hashlib.sha256(V1_PATH.read_bytes()).hexdigest(), V1_SHA256)


if __name__ == "__main__":
    unittest.main()
