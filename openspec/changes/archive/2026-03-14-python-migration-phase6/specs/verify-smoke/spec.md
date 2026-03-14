## verify-smoke

Health checks, scoped smoke fix agent, and phase-end E2E orchestration.

### Requirements

#### VS-HEALTH-URL — Extract health check URL
- Parse localhost:PORT pattern from smoke command string
- Return `http://localhost:{port}` or empty string

#### VS-HEALTH — HTTP health check
- Poll URL with configurable timeout (default 30s)
- Accept any 2xx/3xx status as success
- 1-second polling interval
- Return success/timeout boolean

#### VS-SMOKE-FIX — Scoped smoke fix agent
- Multi-retry loop (configurable max_retries, default 3)
- Get modified files from merge commit, change scope from state
- Multi-change context: if last_smoke_pass_commit exists, find all merges since
- Build fix prompt via wt-orch-core template fix
- Run fix agent via run_claude with sonnet model
- After fix: verify unit tests still pass, revert if broken
- Re-run smoke to verify fix, update smoke_output for next attempt
- Collect screenshots via _collect_smoke_screenshots after each attempt
- Update smoke_fix_attempts and smoke_status in state

#### VS-PHASE-E2E — Phase-end E2E tests
- Run Playwright E2E on main branch after phase completion
- Random port allocation (base + random offset)
- Screenshot collection to wt/orchestration/e2e-screenshots/cycle-N/
- Store results in state.phase_e2e_results array
- Cleanup dev server processes after run
- Copy Playwright test-results/ artifacts
- Non-blocking: failures inform replan, don't block it
- Send notification on pass/fail
- Store failure context for replan consumption
