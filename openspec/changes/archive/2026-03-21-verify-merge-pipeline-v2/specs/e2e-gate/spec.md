# Spec: E2E Gate Improvements

## Requirements

### REQ-E2E-001: Baseline comparison for E2E failures
E2E gate must distinguish between pre-existing failures (already broken on main) and new failures introduced by the change.

**Acceptance Criteria:**
- [ ] AC1: On first E2E run in an orchestration cycle, run Playwright on main and cache failures to `wt/orchestration/e2e-baseline.json`
- [ ] AC2: Baseline includes main_sha, failure list (test file + line), total/passed counts
- [ ] AC3: Baseline is invalidated when main HEAD changes (after a merge)
- [ ] AC4: E2E gate compares change failures against baseline — only NEW failures count as gate failure
- [ ] AC5: Pre-existing failures are logged as warnings, not errors
- [ ] AC6: If baseline run itself fails completely (infra issue), fall back to current behavior (all failures count)

### REQ-E2E-002: Remove manual port allocation
The random port + health check path for non-webServer configs must be removed.

**Acceptance Criteria:**
- [ ] AC1: Remove `E2E_PORT_BASE`, random port allocation, `PW_PORT` env, and `pkill` cleanup
- [ ] AC2: If Playwright config has no `webServer`, skip E2E with diagnostic message explaining why
- [ ] AC3: If Playwright config HAS `webServer`, Playwright manages the dev server lifecycle entirely

### REQ-E2E-003: E2E gate diagnostic logging
When E2E is skipped or fails, the reason must be clearly visible.

**Acceptance Criteria:**
- [ ] AC1: Skip reasons logged: no e2e_command, no playwright config, no webServer, no test files
- [ ] AC2: Baseline comparison results logged: X new failures out of Y total (Z pre-existing)
