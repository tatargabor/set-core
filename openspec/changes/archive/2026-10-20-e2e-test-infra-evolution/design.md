## Context

Agent-generated E2E tests consistently fail when they depend on project-specific test infrastructure (WS mocks, external API stubs, seed data helpers) that either doesn't exist or wasn't extended by previous changes. Each change reinvents helpers locally — duplicating code and missing established patterns. The set-designer v2 run demonstrated this: the chat-and-attachments change wrote tests expecting `data-ws-status='connected'` on the workspace page, but that attribute was only on the dedicated WS test page. The agent had to patch the component retroactively.

Additionally, all generated E2E tests are structural (testid exists, button visible). No tests validate functional flows where user input triggers backend processing and results appear in the UI. Backend logic (e.g. WS message routing, data pipelines) and frontend rendering are tested together or not at all — there's no separation.

The architecture has three layers that must stay separate:
- **Core** (`lib/set_orch/`): abstract hooks, no project-type knowledge
- **Web module** (`modules/web/`): web/Playwright-specific implementations
- **Project**: consumer project's own test helpers that evolve per-change

## Goals / Non-Goals

**Goals:**
- Agents discover and reuse existing test helpers before writing E2E tests
- Agents extend the project's shared test helpers when their feature introduces new infrastructure
- Agents write backend logic tests independently from UI tests
- Agents write 1-2 functional E2E tests per change (full flow, not just structural)
- All of this is driven by planning rules — no new gate blockers

**Non-Goals:**
- Mandating a specific test helper structure (projects evolve organically)
- Creating a test framework — the helpers are project code, not a library
- Blocking merges based on helper usage (advisory only)
- Generating helpers automatically — agents write them based on planning rules

## Decisions

### 1. Profile-driven test infra discovery (Core)

Add `get_test_infra_summary(project_path) -> dict` to the `ProjectType` ABC. Core dispatch calls this and injects the result into `input.md` under a `## E2E Test Infrastructure` section. The dict has:
- `helper_files`: list of paths relative to project root (e.g. `tests/e2e/helpers/ws-mock.ts`)
- `fixture_dirs`: list of fixture directories found
- `patterns_detected`: list of strings describing detected patterns (e.g. "Playwright routeWebSocket", "seed data API at /api/__test/")

Core only defines the interface and the injection point. Returns empty dict if profile doesn't implement it.

### 2. Web module implements scanning (Layer 2)

`WebProjectType.get_test_infra_summary()` scans:
- `tests/e2e/helpers/**/*.ts` — helper files
- `tests/e2e/fixtures/` — fixture directories
- `app/__test/` or `app/(test)/` — test route pages
- `tests/e2e/*.spec.ts` — grep for `routeWebSocket`, `page.request.post.*__test`, seed data patterns

Returns structured summary for dispatch injection.

### 3. Planning rules drive agent behavior (Templates)

Two planning rule templates deployed to consumer projects via `set-project init`:

**`e2e-infra-evolution.md`** (core template, all project types):
```
Before writing E2E tests:
1. Read tests/e2e/helpers/ (or equivalent) — understand what exists
2. Identify what your feature needs that doesn't exist yet
3. Add new helpers/fixtures for your feature's test infrastructure
4. Write E2E tests that USE the helpers, not raw selectors
```

**`e2e-test-layering.md`** (web template):
```
Test your change at three levels:
1. Backend logic (unit/integration) — test WS handlers, API routes, 
   data processing WITHOUT a browser. Use vitest/jest directly.
2. Structural E2E — verify testids, visibility, attributes via Playwright
3. Functional E2E (1-2 tests) — full flow: user types → backend processes → 
   UI updates. These are integration tests, keep them minimal.

When your change has both backend and frontend:
- Test backend separately first (faster feedback, more coverage)
- Write only 1-2 Playwright tests that verify the connection works
```

### 4. Scope check advisory (Core + Profile)

Add optional `check_test_infra_usage(changed_files, project_path) -> list[str]` to profile. Returns warning strings. Web module implements: warns when new `.spec.ts` files contain inline helper functions (like `waitForWsConnected`) that should be in `helpers/`. Non-blocking — logged as advisory in scope check output.

### 5. Web template scaffold

`modules/web/templates/` gains `tests/e2e/helpers/README.md`:
```
# E2E Test Helpers

Shared test utilities for this project's E2E tests.
Each change that introduces new test infrastructure should add helpers here.

Examples:
- ws-mock.ts — WebSocket mock server setup
- seed-data.ts — Test data seeding via API
- auth.ts — Authentication helpers
- navigation.ts — Common page navigation patterns
```

This deploys on `set-project init`, creating the convention. Agents extend it per-change.

## Risks / Trade-offs

- **Risk: Agents ignore planning rules** — Planning rules are guidance, not enforcement. Mitigation: the scope check advisory surfaces when helpers aren't used, giving the agent a nudge on retry.
- **Risk: Helper directory grows without organization** — Projects may accumulate disorganized helpers. Mitigation: the README establishes the convention; review gate can flag duplication.
- **Trade-off: Advisory vs blocking** — We chose non-blocking scope check. Blocking would force compliance but also increase retry cycles for minor issues. The value is in discovery (dispatch injection) more than enforcement.
- **Trade-off: No auto-generation** — We don't generate helpers from specs. Agents write them contextually. This keeps helpers organic and project-appropriate rather than generic boilerplate.
