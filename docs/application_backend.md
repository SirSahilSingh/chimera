# Application Backend (Gate 5)

Gate 5 adds a small FastAPI/SQLAlchemy persistence boundary around the frozen simulator, selected v2 probability artifact, and unchanged Gate 4 decision engine. It is intentionally a modular monolith: one process, one PostgreSQL database, and explicit provider-adapter boundaries.

## Run locally

Install the application dependencies, set `DATABASE_URL` from `.env.example`, then run:

```powershell
python -m uvicorn backend.app.main:app --reload
alembic upgrade head
```

The versioned API is under `/api/v1`; `/health` and `/api/v1/health` expose database/model compatibility without secrets. Application tests use isolated in-memory SQLite; production is configured for PostgreSQL.

## Boundaries

`services/context_builder.py` constructs a decision-time `PaymentFailureEvent` using only persisted observable fields and synthetic placeholders. It does not accept simulator truth. `CaseService` loads the frozen v2 artifact and invokes the existing Gate 4 engine through `Gate4ModelAdapter`; expected-value and policy logic are not duplicated in the API layer.

`DeterministicStubExecutionAdapter` is the only execution adapter in this gate. It records a deterministic provider reference and never calls Razorpay or another provider. The idempotency key is SHA-256 of `case_id|selected_action|decision_run_id`, with a database uniqueness constraint.

`recovery_cases` move through an explicit state machine. Decisions and candidate traces are immutable records. Audit rows are append-only by application design; no update or delete endpoint is exposed.

## Gate 5 limitations

This foundation does not add authentication, frontend views, real provider calls, webhook ingestion, LLM/voice integrations, or recovery-outcome reconciliation. The API case contract currently has no historical-payment table, so an application-created case is evaluated with an empty observable history; this is explicit rather than inferred hidden data. PostgreSQL migrations are supplied, while SQLite is used only for tests.
