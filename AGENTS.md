# Repository Guidelines

## Project Structure & Module Organization

This repository is an early-stage scaffold for Chimera. Keep responsibilities separated by top-level directory:

- `backend/`: server-side code, APIs, integrations, and business logic.
- `frontend/`: client-side application and UI assets.
- `data/`: local fixtures, seed data, and development-only datasets; do not commit secrets.
- `docs/`: architecture notes, API contracts, and contributor documentation.
- `tests/`: cross-component or end-to-end tests; keep unit tests near their implementation when the chosen framework supports it.

Add new files to the narrowest appropriate directory and update `docs/` when introducing a major interface or data contract.

## Build, Test, and Development Commands

No build system, package manifest, or test runner is configured yet. Until tooling is added, inspect the repository with `rg --files`, review changes with `git diff`, and validate documentation links and examples manually. When adding a toolchain, expose standard entry points from the repository root (for example, `npm run dev`, `npm test`, and `npm run build`) and document them here.

## Coding Style & Naming Conventions

Use 2-space indentation for JavaScript, TypeScript, JSON, YAML, and CSS; use the formatter adopted by each ecosystem once configured. Prefer `camelCase` for variables and functions, `PascalCase` for classes and UI components, and `kebab-case` for URL paths and standalone asset names. Use descriptive names and keep modules focused. Add formatting and linting configuration at the repository root so backend and frontend checks are reproducible.

## Testing Guidelines

Tests are not configured yet. Name tests after the behavior under test (for example, `payment-validation.test.ts`) and cover success, validation, and failure paths. Add unit, integration, and end-to-end commands to the root tooling as those layers are introduced; changes to APIs or payment flows should include regression coverage.

## Commit & Pull Request Guidelines

The repository has no commit history yet, so establish a concise imperative convention such as `feat: add payment status endpoint` or `fix: handle invalid webhook signature`. Pull requests should explain the change, identify affected areas, link the relevant issue or requirement, and include screenshots or request/response examples for UI or API changes. Keep each PR focused and note test results or any tooling limitations.

## Security & Configuration Tips

Never commit credentials, payment keys, customer data, or local environment files. Prefer documented environment-variable names with a checked-in `.env.example`; use sanitized fixtures in `data/`. Validate webhook signatures and treat all external input as untrusted.
