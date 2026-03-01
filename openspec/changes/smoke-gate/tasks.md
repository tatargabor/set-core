## 1. Smoke Directives

- [x] 1.1 Add `DEFAULT_SMOKE_COMMAND=""`, `DEFAULT_SMOKE_TIMEOUT=120`, `DEFAULT_DEPLOY_SMOKE_URL=""`, `DEFAULT_DEPLOY_HEALTHCHECK="/api/health"` to defaults section (~line 34)
- [x] 1.2 Add `smoke_command`, `smoke_timeout`, `deploy_smoke_url`, `deploy_healthcheck` parsing in `parse_directives()` with validation
- [x] 1.3 Add the 4 new fields to the JSON output in `parse_directives()`
- [x] 1.4 Thread `smoke_command` and `smoke_timeout` from `monitor_loop()` through to `handle_change_done()` (add parameters or read from directives in state)

## 2. Local Smoke in Verify Gate

- [x] 2.1 In `handle_change_done()`, add Step 2c after build pass and test file check (~line 3810): run `smoke_command` in worktree with `smoke_timeout`, wrapped in `flock --timeout 180 /tmp/wt-smoke-gate.lock` for DB isolation and machine load protection
- [x] 2.2 On smoke pass: set `smoke_result` to "pass", log timing
- [x] 2.3 On smoke fail: same retry logic as test/build — increment `verify_retry_count`, create `retry_context` with smoke output, `resume_change()`
- [x] 2.4 If no `smoke_command`: set `smoke_result` to "skip", continue to next gate
- [x] 2.5 If flock timeout (exit 1 from flock): log warning, set `smoke_result` to "skip", continue (don't block gate)
- [x] 2.6 Add `gate_smoke_ms` to `gate_total_ms` accumulator (~line 3901)

## 3. Deploy Smoke After Merge

- [x] 3.1 Create `deploy_smoke()` function: takes `change_name`, `smoke_command`, `smoke_timeout`, `deploy_smoke_url`, `deploy_healthcheck` — polls healthcheck with curl (30 attempts, 10s apart), then runs `SMOKE_BASE_URL=$url $smoke_command`
- [x] 3.2 On healthcheck timeout: log warning, send notification, skip smoke, return 0
- [x] 3.3 On smoke fail: log warning, send notification (advisory), store `deploy_smoke_result` "fail", return 0
- [x] 3.4 On smoke pass: store `deploy_smoke_result` "pass"
- [x] 3.5 Call `deploy_smoke()` from `merge_change()` Case 3 (normal merge) after `archive_change()`, only if both `deploy_smoke_url` and `smoke_command` are non-empty

## 4. Decomposition Prompt & Planning Guide

- [x] 4.1 Add smoke test awareness hint to spec-mode decomposition prompt (after shared resource rule, ~3 lines)
- [x] 4.2 Add same hint to brief-mode decomposition prompt
- [x] 4.3 Add smoke test coverage section to `docs/planning-guide.md`

## 5. TUI Smoke Display

- [ ] 5.1 In `gui/tui/orchestrator_tui.py` `format_gates()`, add `S` indicator for `smoke_result` field between B and R
- [ ] 5.2 Update `init_state()` to include `smoke_result`, `deploy_smoke_result` fields (null initial values)
