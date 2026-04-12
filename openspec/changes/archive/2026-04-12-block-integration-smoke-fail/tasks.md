# Tasks

## 1. Directive plumbing (core)

- [x] 1.1 Add `integration_smoke_blocking: bool = True` field to the `Directives` dataclass in `lib/set_orch/engine.py` (near the other boolean gate flags) [REQ: Directive integration_smoke_blocking controls smoke-phase blocking]
- [x] 1.2 Add `d.integration_smoke_blocking = _bool(raw, "integration_smoke_blocking", d.integration_smoke_blocking)` to `parse_directives` [REQ: Directive integration_smoke_blocking controls smoke-phase blocking]
- [x] 1.3 Verify no other parse path reads this field — the state writeback pipeline picks up any new dataclass field automatically via `asdict(directives)` [REQ: Directive integration_smoke_blocking controls smoke-phase blocking]

## 2. Merger: make smoke blocking and skip Phase 2 on smoke fail (core)

- [x] 2.1 In `lib/set_orch/merger.py` around line 1230 (start of the two-phase block), read `smoke_blocking` from the directives dict loaded earlier in the function (or add a load if not present). Use `state.extras.get("directives", {}).get("integration_smoke_blocking", True)` with the `True` default matching the Directives dataclass [REQ: Directive integration_smoke_blocking controls smoke-phase blocking]
- [x] 2.2 In the smoke-fail branch (around line 1262-1274 where `_smoke_failed = True` is set today), if `smoke_blocking` is True: persist the smoke output to `integration_e2e_output`, set `change.status = "integration-e2e-failed"` via `update_change_field`, build a retry context via `_build_gate_retry_context` with a smoke-specific preamble, save the retry context to state, and return `False` from `_run_integration_gates` [REQ: Integration e2e smoke phase blocks the merge by default]
- [x] 2.3 Skip Phase 2 (own tests) entirely when smoke blocks — the current `if _use_two_phase and own_specs` branch at line 1296 should NOT run. Use an early `return False` in the smoke-fail branch [REQ: Integration e2e smoke phase blocks the merge by default]
- [x] 2.4 When `smoke_blocking` is False: preserve the existing behavior (WARNING log, `_smoke_failed = True`, continue to Phase 2) so operators who explicitly opted out keep their old flow [REQ: Directive integration_smoke_blocking controls smoke-phase blocking]
- [x] 2.5 Build the smoke-failure retry context (`_build_smoke_retry_context` helper): preamble + sibling spec file names joined with newlines + first 1500 chars of smoke output via `smart_truncate_structured` + closing hint about `test.afterEach` and `testing-conventions.md` [REQ: Smoke-failure retry context helps the agent]
- [x] 2.6 Increment `integration_e2e_retry_count` on smoke fail the same way Phase 2 does, so the retry limit is enforced consistently across both failure paths [REQ: Integration e2e smoke phase blocks the merge by default]

## 3. Tests — `tests/unit/test_merger_smoke_blocking.py` (new file)

- [x] 3.1 Create the file with standard scaffolding (sys.path, imports from set_orch.merger, tmp_path fixture, FakeGateConfig) [REQ: all]
- [x] 3.2 `test_smoke_fail_blocks_merge_default`: construct a state file with a change, monkeypatch `run_command` so the smoke call returns exit_code=1 with a realistic Playwright failure output referencing a sibling spec. Call `_run_integration_gates` with no explicit directive (default True). Assert: (a) return value is False, (b) own-tests call was NOT made (run_command was called exactly once), (c) `change.status` in state is `"integration-e2e-failed"`, (d) `change.retry_context` in state mentions the sibling spec [REQ: Integration e2e smoke phase blocks the merge by default]
- [x] 3.3 `test_smoke_pass_lets_merge_proceed`: smoke call returns exit_code=0, own-tests call returns exit_code=0. Assert return value is True and `change.status` is unchanged [REQ: Integration e2e smoke phase blocks the merge by default]
- [x] 3.4 `test_directive_override_preserves_old_behavior`: set `state.extras["directives"]["integration_smoke_blocking"] = False`. Smoke fails, own-tests pass. Assert return value is True (merge proceeds) and a WARNING log mentions "smoke" and "non-blocking" [REQ: Directive integration_smoke_blocking controls smoke-phase blocking]
- [x] 3.5 `test_retry_context_structure`: smoke fail with multi-line realistic output. Inspect the retry_context string: starts with smoke-phase preamble, lists sibling specs, contains Playwright-looking failure lines, ends with testing-conventions.md reference [REQ: Smoke-failure retry context helps the agent]
- [x] 3.6 `test_retry_count_increments_on_smoke_fail`: call `_run_integration_gates` with a change that has `integration_e2e_retry_count = 0` in extras. After a smoke-fail+blocked call, read the state and assert `integration_e2e_retry_count == 1` [REQ: Integration e2e smoke phase blocks the merge by default]

## 4. Regression check

- [x] 4.1 Run the full existing regression suite (`test_e2e_baseline_cache`, `test_gate_e2e_timeout`, `test_verifier_gate_order`, `test_gate_runner::TestTruncateGateOutput`) — all must still pass [REQ: all]
- [x] 4.2 Run any existing merger tests — no new failures [REQ: all]

## 5. Documentation

- [x] 5.1 Grep `docs/` for `integration_smoke_blocking` — if any existing doc mentions it, update. If not, skip [REQ: Directive integration_smoke_blocking controls smoke-phase blocking]
- [x] 5.2 Grep `docs/` for "smoke" and "non-blocking" in the same line — if the old behavior was documented, update the wording [REQ: Integration e2e smoke phase blocks the merge by default]
