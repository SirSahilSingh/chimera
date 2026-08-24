# Gate 1 Simulator

The deterministic simulator is implemented in `backend/chimera_simulator/`. It has no database, API, frontend, policy engine, ML model, or provider integration.

## Modules

- `config.py`: loads and validates the frozen JSON-compatible YAML configuration and computes its SHA-256 hash.
- `models.py`: separates `PaymentFailureEvent`/`ObservableContext` from internal `HiddenState` and `SimulatorOutcome`.
- `context.py`: applies the `source_timestamp <= decision_timestamp` cutoff.
- `seeds.py`: validates split ranges and derives deterministic event/action seeds.
- `simulator.py`: generates customers, histories, events, hidden truth, action probabilities, and seven-day outcomes.
- `diagnostics.py`: reports distributions, clamp rates, recovery rates, and action costs.

## Local generation

Use the repository's bundled Python runtime or an equivalent Python 3.12 environment:

```powershell
python backend/scripts/generate_simulator.py `
  --split arena_development `
  --seed 400000 `
  --count 100 `
  --events-output data/simulator_v1/dev_seed_400000.events.jsonl `
  --truth-output data/simulator_v1/dev_seed_400000.truth.jsonl `
  --diagnostics-output data/simulator_v1/dev_seed_400000.diagnostics.json
```

The events file is decision-facing only. The truth file is for evaluation diagnostics and contains hidden simulator state and outcomes. The same simulator version, split, seed, event index, and configuration reproduce identical records.

The configuration is JSON-compatible YAML so the simulator can use Python's standard library without adding a YAML dependency. Its raw bytes are hashed; any outcome-affecting change requires a new simulator version under the frozen Gate 0 procedure.

## Development diagnostics

Run cross-tab diagnostics over the five documented development seeds:

```powershell
python backend/scripts/run_development_diagnostics.py `
  --split arena_development `
  --seeds 400000 410000 420000 430000 440000 `
  --count-per-seed 1000 `
  --output data/simulator_v1/dev_diagnostics_5000.json
```

The report includes root-cause/action, segment/action, incident-flag/action, internal environment/action, and root-cause/segment best-action breakdowns. Diagnostic near-ties use a 0.01 absolute probability gap; this is a reporting threshold and does not alter simulator behavior.
