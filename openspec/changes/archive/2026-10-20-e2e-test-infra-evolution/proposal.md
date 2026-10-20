## Why

Agent-generated E2E tests fail because they depend on project-specific test infrastructure (WS mocks, seed data APIs, test routes) that doesn't exist yet or wasn't extended by previous changes. Each change reinvents helpers locally instead of building on a shared, evolving test infrastructure layer. Additionally, all current E2E tests are structural (testid exists, button visible) — no tests validate actual end-to-end functional flows (user types → brain processes → preview updates). The framework needs to ensure agents discover, extend, and reuse project-specific test infrastructure, and write tests at the right abstraction level.

## What Changes

### Layer 1: Core (`lib/set_orch/`) — abstract mechanisms

- **Dispatch E2E context injection**: dispatcher calls `profile.get_test_infra_summary()` to read the project's existing test helper/fixture directory structure and includes it in the agent's `input.md`. Core provides the hook, not the implementation.
- **`ProjectType` ABC extension**: new abstract method `get_test_infra_summary(project_path) -> dict` returns a structured summary of existing test infrastructure (helper files, fixture dirs, mock patterns). Core defines the interface.
- **Scope check hook**: `verify.py` scope check gains an optional `check_test_infra_usage()` call via profile — warns when E2E tests bypass shared helpers. Non-blocking, profile-driven.

### Layer 2: Web module (`modules/web/`) — web-specific patterns

- **`WebProjectType.get_test_infra_summary()`**: implements the abstract method — scans `tests/e2e/helpers/`, `tests/e2e/fixtures/`, detects Playwright patterns (routeWebSocket, test route pages, seed data APIs), returns structured summary.
- **Web template scaffold**: `modules/web/templates/` gains a `tests/e2e/helpers/README.md` that instructs agents on the shared helper convention. Deploys via `set-project init`.
- **Test layering planning rules** (web-specific): instruct agents to write tests at three levels:
  1. **Unit/integration** for backend logic (e.g. WS message handling, billing API mock, data processing) — no browser, fast, high coverage
  2. **Structural E2E** (existing pattern) — testids, visibility, attributes
  3. **Functional E2E** — 1-2 end-to-end flow tests per change that exercise the full pipeline (user action → backend processing → UI state update)
- **Backend/frontend test separation rule**: when a change introduces both server-side logic (WS handler, API route, data pipeline) and UI components, the planning rule instructs agents to test the backend logic independently first, then write only 1-2 integration E2E tests that verify the full stack connection.

### Layer 3: Project level — lives in the consumer project, evolves with changes

- **`tests/e2e/helpers/` directory**: project-specific, created by `set-project init`, extended by each change's agent. Contains the actual mocks/fixtures/utilities (WS mock server, billing API stub, auth fixture, seed data helpers). This is NOT in set-core — it lives in the project and grows organically.
- **Planning rule template for E2E infra evolution** (`templates/core/rules/`): instructs agents to scan existing helpers before writing E2E tests, identify gaps, extend the shared helpers, then write tests that use them. Deploys to consumer projects. The rule is generic — the helpers it discovers are project-specific.

## Capabilities

### New Capabilities
- `e2e-infra-evolution`: Abstract mechanism for test infrastructure discovery and evolution. Core provides `ProjectType.get_test_infra_summary()` hook + dispatch injection. Web module implements scanning. Planning rules (deployed to projects) instruct agents on the scan → extend → use workflow.
- `e2e-test-layering`: Test strategy guidance for agents. Planning rules define three test levels (unit, structural E2E, functional E2E) and when each applies. Web module provides web-specific rules (Playwright patterns, backend/frontend separation). Core provides no code — this is purely planning rule templates.

### Modified Capabilities
- `verify-gate`: Scope check step gains optional profile-driven warning for E2E tests that bypass shared helpers

## Impact

### Core (`lib/set_orch/`)
- `profile_types.py` — new `get_test_infra_summary()` abstract method on `ProjectType`
- `dispatch.py` — calls `profile.get_test_infra_summary()`, injects result into `input.md`
- `verify.py` — scope check calls `profile.check_test_infra_usage()` (optional, non-blocking)

### Web module (`modules/web/`)
- `set_project_web/profile.py` — implements `get_test_infra_summary()` and `check_test_infra_usage()`
- `modules/web/templates/rules/` — test layering and backend/frontend separation planning rules
- `modules/web/templates/` — `tests/e2e/helpers/README.md` scaffold

### Templates (deploy to consumer projects)
- `templates/core/rules/e2e-infra-evolution.md` — generic "scan → extend → use" planning rule
- Deployed via `set-project init`, lives in project's `.claude/rules/`
