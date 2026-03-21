# Tasks: visual-e2e-smoke-tests

## 1. Runtime error detection in E2E gate

- [x] 1.1 Add `_check_e2e_runtime_errors()` to `lib/set_orch/verifier.py` — scan E2E output for runtime error indicators (React hydration, RSC boundary, console.error, Next.js error overlay markers)
- [x] 1.2 Call from `_execute_e2e_gate()` after E2E run — if errors found, append warning to gate result output (not blocking, informational)
- [x] 1.3 Make error indicator list a module-level constant `E2E_RUNTIME_ERROR_INDICATORS` — extensible without code change

## 2. Screenshot on every E2E run

- [x] 2.1 In `_execute_e2e_gate()`, add `PLAYWRIGHT_SCREENSHOT=on` to the env dict passed to the E2E command
- [x] 2.2 Ensure screenshot collection (existing copytree logic) works with `screenshot: 'on'` mode (more files than failure-only)

## 3. Profile extension for smoke test generation

- [x] 3.1 Add `generate_smoke_e2e(self, project_path: str) -> str | None` method to `NullProfile` in `lib/set_orch/profile_loader.py` — returns None
- [x] 3.2 In `lib/project/deploy.sh`, call `generate_smoke_e2e` during deploy — if result is non-empty, write to `e2e/smoke-routes.spec.ts` in project
- [x] 3.3 Document the extension point for set-project-web implementation

## 4. set-project-web follow-up (separate repo — tasks for reference only)

- [ ] 4.1 Implement `generate_smoke_e2e()` in WebProjectType — scan `app/[locale]/**/page.tsx`, generate Playwright test
- [ ] 4.2 Route discovery: convert file paths to URLs, handle dynamic segments with seed data lookup
- [ ] 4.3 Generated test template: visit route, waitForLoadState('networkidle'), assert no pageerror, no error boundary DOM element, body has content
- [ ] 4.4 Deploy via `set-project init --project-type web` — auto-generates `e2e/smoke-routes.spec.ts`

## 5. Verification

- [x] 5.1 Verify runtime error detection catches "Functions are not valid as a child" pattern
- [x] 5.2 Verify screenshots are captured on pass (not just failure)
- [x] 5.3 Verify NullProfile.generate_smoke_e2e() returns None (no-op for non-web projects)
