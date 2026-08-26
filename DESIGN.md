# CHIMERA Control Room

## Visual direction

CHIMERA is an autonomous Revenue Recovery Intelligence system presented as a fintech incident-response control room. The operator uses it under task pressure to see what failed, understand the observable pattern, inspect the stored decision, and act only when backend authority allows it.

## Visual world

- Near-black graphite shell and workspace: `#0a1113`, `#0d1517`, `#132023`.
- Phosphor mint for recovered, selected, and authoritative states: `#55d6a7`.
- Amber for revenue at risk and intervention required: `#f2b86b`.
- Red only for unresolved outcome or actual error: `#f07b7b`.
- Thin technical rules, squared 4–10px corners, shallow panel depth, and dense control-room modules.
- IBM Plex Sans/system fallback for operational copy; tabular numerals and monospace only for identifiers and provider references.

## Information architecture

- **Command Center** opens with the workflow thesis, revenue at risk, active problem signal, failure breakdown, observed root-cause patterns, and stored activity.
- **Recovery Operations** turns the case list into an operational queue with status, diagnosis, intervention, and outcome columns.
- **Decision Room** leads with the recovery lifecycle, observable diagnosis, ranked candidate actions, reasoning, constraints, intervention, outcome, and activity timeline.
- **Intelligence** contains failure-pattern and observed-performance views. **Audit Trail** contains stored milestones only.

## Interaction rules

The browser renders API-backed values and aggregates only the loaded records. It never recalculates probabilities, expected value, ranking, policy, fatigue, or outcomes. Candidate actions are presented as ranked cards; blocked actions retain their stored reasons. Explanations are informational and append-only. Execution requires backend eligibility and an explicit confirmation dialog.

## Responsive behavior

Desktop uses a persistent operations rail and two-column intelligence modules. Mobile collapses the rail to a compact navigation strip, stacks workflow modules, preserves action-card scanability, and lets dense case tables scroll inside their own panel without widening the page.
