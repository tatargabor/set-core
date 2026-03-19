## 1. Test Runner & Scope Checks

- [x] 1.1 Implement `run_tests_in_worktree()` — execute test command in worktree with timeout, capture exit code + truncated output, return `TestResult` dataclass
- [x] 1.2 Implement `_parse_test_stats()` — parse Jest/Vitest/Playwright output for passed/failed/suites counts
- [x] 1.3 Implement `verify_merge_scope()` — post-merge diff HEAD~1, filter artifact/config paths, return pass/fail
- [x] 1.4 Implement `verify_implementation_scope()` — pre-merge diff vs merge-base, same filter, return `ScopeCheckResult`

## 2. Review & Rules

- [x] 2.1 Implement `build_req_review_section()` — read requirements + also_affects_reqs from state, look up titles from digest, build prompt section
- [x] 2.2 Implement `review_change()` — generate diff, build review prompt via template, run_claude with model escalation, return `ReviewResult`
- [x] 2.3 Implement `evaluate_verification_rules()` — read project-knowledge.yaml rules, match trigger globs against changed files, return error/warning counts

## 3. Smoke & Health

- [x] 3.1 Implement `extract_health_check_url()` — regex parse localhost:PORT from smoke command
- [x] 3.2 Implement `health_check()` — HTTP poll with timeout, accept 2xx/3xx
- [x] 3.3 Implement `smoke_fix_scoped()` — multi-retry fix agent with test verification and smoke re-check
- [x] 3.4 Implement `_collect_smoke_screenshots()` — collect Playwright artifacts from worktree
- [x] 3.5 Implement `run_phase_end_e2e()` — phase-end Playwright on main, screenshot collection, state storage

## 4. Polling & Gate Pipeline

- [x] 4.1 Implement `poll_change()` — read loop-state.json, token accumulation with _prev counters, status dispatch
- [x] 4.2 Implement `handle_change_done()` — full verify gate pipeline: build → test → e2e → scope → test files → review → rules → verify → merge queue
- [x] 4.3 Implement retry logic helpers — token snapshot, retry_context building, verify_retry_count management

## 5. CLI Bridge

- [x] 5.1 Add `set-orch-core verify` subcommands to cli.py — run-tests, review, evaluate-rules, check-merge-scope, check-impl-scope, health-check, poll, handle-done, smoke-fix, phase-e2e, build-req-section, extract-health-url
- [x] 5.2 Replace verifier.sh functions with thin wrappers calling `set-orch-core verify *`

## 6. Tests

- [x] 6.1 Tests for test runner — run_tests_in_worktree, _parse_test_stats (Jest, Vitest, Playwright formats)
- [x] 6.2 Tests for scope checks — verify_merge_scope, verify_implementation_scope (impl files, only artifacts, empty diff)
- [x] 6.3 Tests for review — build_req_review_section (with/without digest, empty reqs), extract_health_check_url
- [x] 6.4 Tests for verification rules — evaluate_verification_rules (error/warning/no rules/no file)
- [x] 6.5 Tests for poll — token accumulation logic, status dispatch routing
