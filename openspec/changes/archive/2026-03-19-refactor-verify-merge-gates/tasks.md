## 1. Bug Fixes (P0/P1)

- [x] 1.1 Fix `_check_completion` to return False when `state.merge_queue` is non-empty — add guard at top of function in engine.py [REQ: completion-detection-shall-respect-merge-queue]
- [x] 1.2 Fix `_verify_gates_already_passed` to check e2e_result, rules result, and spec_coverage_result from change.extras in addition to test_result, build_result, review_result, scope_check [REQ: verify-gate-results-shall-be-preserved-across-monitor-restart]
- [x] 1.3 Fix `_recover_verify_failed` to NOT increment verify_retry_count — remove L703-705 counter increment, keep only the resume_change call and retry_context rebuild [REQ: crash-recovery-retry-count-shall-not-double-increment]
- [x] 1.4 Add unit tests for `_check_completion` with non-empty merge_queue scenario [REQ: completion-detection-shall-respect-merge-queue]
- [x] 1.5 Add unit tests for `_verify_gates_already_passed` with failed rules/spec_verify in extras [REQ: verify-gate-results-shall-be-preserved-across-monitor-restart]
- [x] 1.6 Add unit test for `_recover_verify_failed` verifying retry count is NOT incremented [REQ: crash-recovery-retry-count-shall-not-double-increment]

## 2. GateResult and GatePipeline Core

- [x] 2.1 Create `lib/wt_orch/gate_runner.py` with `GateResult` dataclass (gate_name, status, output, duration_ms, stats) [REQ: gateresult-captures-gate-outcome]
- [x] 2.2 Implement `GatePipeline` class with `register_gate(name, executor_fn)` and `run()` method that executes gates in order [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 2.3 Implement skip logic: if `gc.should_run(name)` is False, append skipped GateResult without calling executor [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 2.4 Implement blocking failure handling: check retry budget, set verify-failed status, store retry context, call resume_change, stop pipeline [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 2.5 Implement non-blocking failure handling: set status to warn-fail, continue pipeline [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 2.6 Implement `commit_results()` — single `locked_state` block writing all gate results, timings, and final status [REQ: batch-state-update-after-pipeline-completion]
- [x] 2.7 Add unit tests for GatePipeline: skip, pass, blocking-fail-with-retry, blocking-fail-exhausted, warn-fail scenarios [REQ: gatepipeline-orchestrates-gate-execution]

## 3. Gate Executors

- [x] 3.1 Extract build gate executor from handle_change_done Step 1 (lines 1571-1635) into `_execute_build_gate(change, wt_path, gc, pm) -> GateResult` [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 3.2 Extract test gate executor from Step 2 (lines 1636-1685) into `_execute_test_gate(change, wt_path, test_command, test_timeout) -> GateResult` [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 3.3 Extract e2e gate executor from Step 3 (lines 1686-1785) into `_execute_e2e_gate(change, wt_path, e2e_command, e2e_timeout) -> GateResult` [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 3.4 Extract scope check executor from Step 4 (lines 1786-1815) into `_execute_scope_gate(change, wt_path) -> GateResult` [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 3.5 Extract test_files check executor from Step 4b (lines 1817-1865) into `_execute_test_files_gate(change, wt_path, gc) -> GateResult` [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 3.6 Extract review gate executor from Step 5 (lines 1866-1923) into `_execute_review_gate(change, wt_path, gc, review_model, state_file, design_snapshot_dir) -> GateResult` [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 3.7 Extract rules gate executor from Step 5b (lines 1924-1939) into `_execute_rules_gate(change, wt_path, event_bus) -> GateResult` [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 3.8 Extract spec_verify executor from Step 6 (lines 1941-1999) into `_execute_spec_verify_gate(change, wt_path, gc) -> GateResult` [REQ: gatepipeline-orchestrates-gate-execution]

## 4. Rewire handle_change_done

- [x] 4.1 Rewrite `handle_change_done` to use GatePipeline: keep pre-pipeline logic (context tokens, retry tracking, uncommitted check, merge-rebase fast path), then delegate to pipeline.run() [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 4.2 Wire build gate with separate retry counter (`build_fix_attempt_count` in extras) — pipeline supports `uses_own_retry_counter` flag [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 4.3 Wire review gate with configurable extra retry via `gc.review_extra_retries` [REQ: review-extra-retry-configurable]
- [x] 4.4 Preserve VERIFY_GATE event emission with gate_profile, gates_skipped, gates_warn_only data [REQ: gatepipeline-orchestrates-gate-execution]
- [x] 4.5 Run existing tests (`tests/unit/test_verifier.py`, `tests/test_gate_profiles.py`) — must pass unchanged [REQ: gatepipeline-orchestrates-gate-execution]

## 5. GateConfig Extension

- [x] 5.1 Add `review_extra_retries: int = 1` field to GateConfig dataclass in gate_profiles.py [REQ: review-extra-retry-configurable]
- [x] 5.2 Add `review_extra_retries` to gate_hints and directive override paths in `resolve_gate_config` [REQ: review-extra-retry-configurable]

## 6. Screenshot Collection Dedup

- [x] 6.1 Create unified `collect_screenshots(change_name, source_dir, category, attempt=None)` function using WtRuntime paths [REQ: unified-screenshot-collection]
- [x] 6.2 Replace merger.py `_collect_smoke_screenshots` calls with unified function [REQ: unified-screenshot-collection]
- [x] 6.3 Replace verifier.py `_collect_smoke_screenshots` calls with unified function [REQ: unified-screenshot-collection]
- [x] 6.4 Remove both old `_collect_smoke_screenshots` implementations [REQ: unified-screenshot-collection]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN all changes have status "done" AND merge_queue is non-empty THEN _check_completion returns False [REQ: completion-detection-shall-respect-merge-queue, scenario: all-changes-verified-but-merge-queue-non-empty]
- [x] AC-2: WHEN merge_change throws exception AND change stays "done" in merge_queue THEN _check_completion returns False and next poll retries merge [REQ: completion-detection-shall-respect-merge-queue, scenario: merge-exception-leaves-change-in-done-status]
- [x] AC-3: WHEN change has verifying status with test/build/review/scope pass BUT rules result is fail THEN _verify_gates_already_passed returns False [REQ: verify-gate-results-shall-be-preserved-across-monitor-restart, scenario: change-in-verifying-with-failed-rules-gate-after-restart]
- [x] AC-4: WHEN change has verify-failed status after restart THEN _recover_verify_failed resumes without incrementing verify_retry_count [REQ: crash-recovery-retry-count-shall-not-double-increment, scenario: normal-verify-failed-recovery]
- [x] AC-5: WHEN GatePipeline runs with a skipped gate THEN executor is NOT called AND result status is "skipped" [REQ: gatepipeline-orchestrates-gate-execution, scenario: skipped-gate-produces-skip-result]
- [x] AC-6: WHEN a blocking gate fails AND retries available THEN pipeline increments counter, sets verify-failed, resumes, and stops [REQ: gatepipeline-orchestrates-gate-execution, scenario: blocking-failure-triggers-retry-or-fail]
- [x] AC-7: WHEN pipeline completes THEN all results written in single locked_state block [REQ: batch-state-update-after-pipeline-completion, scenario: all-results-written-atomically]
- [x] AC-8: WHEN GateConfig has review_extra_retries=0 THEN review retry limit equals other gates [REQ: review-extra-retry-configurable, scenario: custom-review-extra-retry]
- [x] AC-9: WHEN smoke tests produce screenshots THEN collect_screenshots uses WtRuntime paths consistently [REQ: unified-screenshot-collection, scenario: smoke-screenshots-collected-consistently]
