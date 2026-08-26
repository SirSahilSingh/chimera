# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Inferred from the approved architecture: Next.js with TypeScript for the operator-facing frontend, FastAPI for the backend, and PostgreSQL for persistence.

## Users

Primary user: a recovery operations analyst who reviews payment-failure cases, understands CHIMERA's stored deterministic decision, and executes an approved recovery action when the backend state machine permits it.

Secondary users include risk or operations managers reviewing aggregate case activity, and technical/demo reviewers inspecting explainability, auditability, and safety boundaries.

## Product Purpose

CHIMERA helps operators recover failed payments through a transparent workflow: inspect observable case context, generate a deterministic decision, compare candidate economics and constraints, read an optional explanation, and execute the stored decision. Success means an operator can understand and trust the decision without relying on an LLM or recreating backend logic in the UI.

## Positioning

Inferred positioning: auditable recovery operations. CHIMERA combines action-conditioned recovery estimates, expected-value scoring, deterministic policy validation, immutable traces, and optional non-authoritative explanations in one operator workflow.

## Operating Context

The product is a desktop-first operations dashboard for dense case review. The backend is authoritative for cases, decisions, candidate scores, explanations, state transitions, and execution. The frontend consumes the existing versioned API and presents the Command Center, Recovery Cases, and Decision Room workflows.

## Capabilities and Constraints

- Display only API-backed observable data and stored deterministic traces.
- Generate decisions, explanations, and executions through existing backend endpoints.
- Show every candidate action, including blocked actions and reasons.
- Treat Gate 6 explanations as optional, secondary, immutable history.
- Never calculate probabilities, expected value, costs, fatigue, constraints, rankings, or actions in the frontend.
- Never expose API keys, provider credentials, hidden simulator state, latent variables, future outcomes, or counterfactual truth.
- Use integer paise values from the backend and the actual case state machine.

## Brand Commitments

The product name is CHIMERA. The Gate 7 brief requires a serious financial-operations tone: clear, trustworthy, information-dense, restrained, and free of generic SaaS decoration. No specific logo, palette, typography, or visual asset has been committed.

## Evidence on Hand

The repository contains the approved simulator, model, deterministic engine, FastAPI application backend, Gate 6 explanation layer, API contracts, migrations, tests, and synthetic-only data. No real customer data, testimonials, production performance claims, or brand assets are present and must not be fabricated.

## Product Principles

- The backend decides; the frontend explains and facilitates operator action.
- Every displayed economic value must be traceable to stored backend data.
- Optional intelligence must never become a critical dependency.
- Financial actions require explicit state-machine authority and clear operator intent.
- Synthetic evidence must remain clearly distinct from real-world performance claims.

## Accessibility & Inclusion

The Gate 7 brief requires responsive behavior, clear loading/error/empty states, readable dense tables, and accessible action states. Desktop operations use is primary; mobile support is secondary. No additional product-specific accessibility standard has been established.
