# Spec: Visual E2E Smoke Tests

## Requirements

### REQ-VE2E-001: Runtime error detection in E2E gate
The E2E gate must detect client-side runtime errors even when HTTP status is 200.

**Acceptance Criteria:**
- [ ] AC1: After E2E run, scan output for runtime error indicators (React hydration, RSC boundary, console.error)
- [ ] AC2: If runtime errors found in output, add warning to gate result (not blocking — informational for now)
- [ ] AC3: Error indicators are configurable via a list, not hardcoded in gate logic

### REQ-VE2E-002: Screenshot on every E2E run
E2E gate must capture screenshots regardless of pass/fail, for visual review.

**Acceptance Criteria:**
- [ ] AC1: Set `PLAYWRIGHT_SCREENSHOT=on` env var when running E2E command
- [ ] AC2: Screenshots collected to orchestration screenshots dir (existing path)
- [ ] AC3: Works with both webServer-managed and user-configured Playwright setups

### REQ-VE2E-003: Profile extension for smoke test generation
Project-type plugins must be able to generate route-level smoke E2E tests.

**Acceptance Criteria:**
- [ ] AC1: `NullProfile` has `generate_smoke_e2e(project_path) -> str | None` method returning None
- [ ] AC2: Method is called during `set-project init` deploy — if returns content, writes to `e2e/smoke-routes.spec.ts`
- [ ] AC3: Generated test visits each route, waits for hydration, asserts no pageerror, no error boundary in DOM

### REQ-VE2E-004: Route discovery for smoke test generation
The smoke test generator must auto-discover routes from the app directory structure.

**Acceptance Criteria:**
- [ ] AC1: Scan `app/[locale]/**/page.tsx` (or `app/**/page.tsx`) for route paths
- [ ] AC2: Convert file paths to URL paths (e.g., `app/[locale]/kavek/[slug]/page.tsx` → `/hu/kavek/{test-id}`)
- [ ] AC3: Dynamic segments (`[slug]`, `[id]`) use seed data or first-available entity from DB
- [ ] AC4: Route list is deterministic and reproducible
