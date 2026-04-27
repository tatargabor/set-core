# Tasks

## 1. Bug reproduction test (writes first, confirms pre-fix state)

- [x] 1.1 Create `tests/unit/test_gate_e2e_timeout.py` with three failing-first test cases covering: (a) timed-out run, (b) unparseable non-zero exit, (c) real failure that enters baseline comparison [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 1.2 Test case A (`test_timeout_returns_fail`): monkeypatch `subprocess_utils.run_command` and `run_git` so that the first call (worktree e2e) returns `CommandResult(exit_code=-1, timed_out=True, stdout=<real truncated mid-run Playwright output>, stderr="", duration_ms=120000)` and the second call (baseline main run) returns a clean pass. Construct a temporary git-initialised worktree with a minimal `playwright.config.ts` and one `*.spec.ts`. Assert the returned `GateResult` has `status == "fail"` and the `output` contains "timed out" [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 1.3 Test case B (`test_unparseable_nonzero_exit_returns_fail`): same fixtures as A but with `CommandResult(exit_code=2, timed_out=False, stdout="Segmentation fault\n", stderr="", duration_ms=5000)`. Assert `status == "fail"` and the output mentions "no parseable failure list" [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 1.4 Test case C (`test_real_failure_enters_baseline_comparison`): `CommandResult(exit_code=1, timed_out=False, stdout="...\n  1) [chromium] › tests/e2e/foo.spec.ts:45 › Some test\n    Error: ...\n\n  1 failed\n", stderr="", duration_ms=60000)` plus a monkeypatched `_get_or_create_e2e_baseline` returning `{"failures": set()}`. Assert the status is `"fail"` and `"foo.spec.ts:45"` appears in the output header [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 1.5 Add a fourth test case (`test_pre_fix_bug_snapshot`) with the exact inputs from the investigation (timeout + empty baseline) that ASSERTS the pre-fix buggy behavior was `status == "pass"`. This test is a regression fossil: it should pass on pre-fix code (documenting the bug) and MUST be flipped by task 3.2 to assert `status == "fail"` after the fix. Include a clear docstring pointing to the investigation notes [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 1.6 Run the test file once before any fix to confirm: tests A/B/C/D all FAIL (buggy code returns pass); tests 1.2-1.4 fail because the gate returns pass instead of fail; test 1.5 passes on the old code. Record the failing output in a comment in the test file as baseline evidence

## 2. Fix — gate guard clauses (core bug)

- [x] 2.1 Locate `execute_e2e_gate` in `modules/web/set_project_web/gates.py` around line 192 [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 2.2 After the `raw_status = "pass" if e2e_cmd_result.exit_code == 0 else "fail"` line (around line 299) and before the `if raw_status == "pass":` block, add a new `if e2e_cmd_result.timed_out:` guard clause that returns `GateResult("e2e", "fail", output=..., retry_context=...)` with the timeout-specific retry context from the design doc [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 2.3 The timeout guard SHALL return BEFORE any baseline comparison runs. Do NOT compute `wt_failures` or call `_get_or_create_e2e_baseline` after the guard trips [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 2.4 In the existing baseline-comparison branch (around line 321), immediately after `wt_failures = _extract_e2e_failure_ids(e2e_output)`, add a guard: `if not wt_failures: return GateResult("e2e", "fail", ...)` with the unparseable-fail retry context [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 2.5 The unparseable-fail guard SHALL return BEFORE `_get_or_create_e2e_baseline` is called. Do NOT enter the baseline branch with an empty `wt_failures` [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 2.6 Preserve the existing behavior for the case where `wt_failures` is non-empty (real parseable failures): the baseline comparison SHALL still run, still honor `pre_existing` vs `new_failures`, and still emit the `"NEW failures (+ N pre-existing)"` header [REQ: Worktree E2E gate never returns PASS on incomplete runs]

## 3. Fix — raise default timeout

- [x] 3.1 In `lib/set_orch/engine.py`, change the `Directives.e2e_timeout: int = 120` field default (around line 80) to `= 300` [REQ: Default e2e_timeout covers realistic web-suite runtime]
- [x] 3.2 In `lib/set_orch/verifier.py`, change `DEFAULT_E2E_TIMEOUT = 120` (around line 82) to `= 300` [REQ: Default e2e_timeout covers realistic web-suite runtime]
- [x] 3.3 Grep `lib/set_orch/` and `modules/` for any other hardcoded `e2e_timeout.*120` references — there should be none outside test fixtures, but verify. Update any that remain [REQ: Default e2e_timeout covers realistic web-suite runtime]
- [x] 3.4 Verify the `parse_directives` function at `engine.py:142` correctly reads the new default when no override is provided: `d.e2e_timeout = _int(raw, "e2e_timeout", d.e2e_timeout)` — no change needed, just confirm [REQ: Default e2e_timeout covers realistic web-suite runtime]

## 4. Fix — uncap capture, bound storage with pattern preservation

- [x] 4.1 Add a module-level constant `_E2E_CAPTURE_MAX_BYTES = 4 * 1024 * 1024` near the top of `modules/web/set_project_web/gates.py` (after the logger definition, near `E2E_RUNTIME_ERROR_INDICATORS`). Include a comment explaining it is the transient capture ceiling, with downstream storage bounded separately at 32KB [REQ: E2E capture is large; storage is pattern-preserving truncated]
- [x] 4.2 In `execute_e2e_gate` around line 271, change the `run_command` call to pass `max_output_size=_E2E_CAPTURE_MAX_BYTES` (was `4000`) [REQ: E2E capture is large; storage is pattern-preserving truncated]
- [x] 4.3 In `_get_or_create_e2e_baseline` around line 149, change the `run_command` call to pass `max_output_size=_E2E_CAPTURE_MAX_BYTES` (was `8000`) [REQ: E2E capture is large; storage is pattern-preserving truncated]
- [x] 4.4 In `execute_e2e_gate`, the `GateResult(output=e2e_output[:4000], ...)` construction (around line 420) — remove the `[:4000]` slice and pass the full `e2e_output`. The gate runner is now responsible for truncation at the storage boundary [REQ: E2E capture is large; storage is pattern-preserving truncated]
- [x] 4.5 In `lib/set_orch/gate_runner.py`, add a module-level constant `_PLAYWRIGHT_FAIL_PATTERN` and a helper `_truncate_gate_output(gate_name, output)` that uses `smart_truncate_structured(output, 32000, keep_patterns=_PLAYWRIGHT_FAIL_PATTERN)` for `"e2e"` and plain `smart_truncate(output, 2000)` otherwise [REQ: E2E capture is large; storage is pattern-preserving truncated]
- [x] 4.6 Replace both gate_runner output-write sites (around lines 292 and 434) to call `_truncate_gate_output(entry.name, result.output)` or `_truncate_gate_output(r.gate_name, r.output)` instead of the existing `smart_truncate(..., 2000)` or `[:2000]` head-slice [REQ: E2E capture is large; storage is pattern-preserving truncated]
- [x] 4.7 Import `smart_truncate_structured` alongside `smart_truncate` at the top of `gate_runner.py` [REQ: E2E capture is large; storage is pattern-preserving truncated]

## 5. Flip the regression test and verify

- [x] 5.1 After tasks 2-4 are done, run the test file again — tests A/B/C should now PASS (gate returns fail as expected) [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 5.2 Edit test case D (the `test_pre_fix_bug_snapshot` fossil) to flip its assertion from `status == "pass"` to `status == "fail"`, turning it into a permanent regression guard. Update its docstring to say "formerly asserted buggy pass behavior — now asserts the fixed fail behavior" [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 5.3 Run the full file again — all four tests should now pass [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 5.4 Run the existing test suite (`pytest tests/unit/`) to confirm no unrelated regressions [REQ: Worktree E2E gate never returns PASS on incomplete runs]

## 6. Documentation and release notes

- [x] 6.1 Grep `docs/` for any mention of `e2e_timeout.*120` and update to 300 [REQ: Default e2e_timeout covers realistic web-suite runtime]
- [x] 6.2 Grep `docs/` for any text that implies the worktree-stage e2e gate is authoritative — the docs should reflect that the gate was previously unreliable and has been hardened [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [x] 6.3 Add a short entry to the relevant changelog/release-notes file under set-core that summarizes: "Worktree-stage e2e gate no longer masks timeouts as PASS. Default e2e_timeout raised 120 → 300. Output buffer raised 4K → 32K." [REQ: Default e2e_timeout covers realistic web-suite runtime]

## 7. Manual end-to-end smoke (deferred to next real orchestration)

- [ ] 7.1 After merging this change, start a fresh orchestration on a realistic web template project [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [ ] 7.2 Confirm the worktree-stage e2e gate reports a realistic duration in the 100-250s range (not always ~120s cliffed) [REQ: Default e2e_timeout covers realistic web-suite runtime]
- [ ] 7.3 Verify via the dashboard that no change shows `e2e=pass` immediately followed by `integration_e2e=fail` (the signature of the old bug) [REQ: Worktree E2E gate never returns PASS on incomplete runs]
- [ ] 7.4 If possible, intentionally break a spec and confirm the worktree-stage gate catches it (reports fail) without requiring the merger to discover it [REQ: Worktree E2E gate never returns PASS on incomplete runs]
