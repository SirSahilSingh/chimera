# Gate 7 Operator Frontend

The frontend is a Next.js 14 + TypeScript operator workspace under `frontend/`. It is a presentation and workflow layer over the existing FastAPI application backend. The backend remains authoritative for decisions, candidate economics, policy constraints, state transitions, explanations, and execution.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

By default, the browser calls the same-origin `/api/v1` path and Next.js proxies it to `http://localhost:8000`; this avoids requiring CORS for local development. Set `CHIMERA_API_PROXY_URL` when the local backend lives elsewhere. Set `NEXT_PUBLIC_API_BASE_URL` only for a separately hosted API that already has CORS configured. Provider credentials and LLM keys remain server-side.

## Screens and workflow

- `/` — Revenue Recovery Command Center: revenue at risk, active-problem flow, observed failure breakdown, root-cause patterns, recent stored activity, and recent cases.
- `/cases` — Recovery Operations queue with all/active/recovered/escalated/unresolved, failure-pattern, and intervention filters.
- `/cases/{caseId}` — Decision Room: lifecycle, observable diagnosis, ranked candidate actions, deterministic reasoning, policy constraints, explanation/history, intervention, outcome, and stored activity.
- `/intelligence/failures` — observed failure-pattern distribution and root-cause view.
- `/intelligence/performance` — observed intervention outcomes with an explicit non-causal boundary.
- `/audit` — chronological case/decision/execution/outcome milestones returned by the existing API.

The browser calls only the existing `/api/v1` endpoints. It never calculates probabilities, expected values, costs, fatigue, constraints, rankings, or actions. It displays stored candidate ranks and values as returned by the backend. Explanation records are treated as immutable history; explicit explanation requests create new records. Execution is available only when the backend case status is `DECIDED`, and the confirmation explicitly states that the stored deterministic decision will be executed.

## States and safety

Loading, empty, unavailable-backend, not-found, invalid-transition, explanation-fallback, blocked-candidate, and executed states are surfaced without exposing stack traces or secrets. Synthetic environment labeling is visible in the top bar. The interface is desktop-first and collapses navigation, fact strips, metrics, and dense tables structurally for smaller screens.

The current API does not expose friendly `REC-###` identifiers, customer names, granular audit rows, true recovered amounts, or historical trend series. The UI therefore uses external event IDs, stored customer/payment identifiers, stored timestamps, case amounts, and honest pending/observed states rather than inventing those fields.
