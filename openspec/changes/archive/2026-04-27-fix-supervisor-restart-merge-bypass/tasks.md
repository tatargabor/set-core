# Tasks: fix-supervisor-restart-merge-bypass

## 1. Code change

- [ ] 1.1 Modify `lib/set_orch/engine.py` `_cleanup_orphans` Phase 1b (lines 389-415) to branch on `_verify_gates_already_passed(change)`:
  - If True: keep existing behavior (append to `merge_queue`).
  - If False: set `change.status = "running"`, `change.ralph_pid = None`, log a `WARNING` with the change name and the fact that gates were incomplete. Do NOT touch `merge_queue`.
  [REQ: orphan-cleanup/phase-1b-must-not-bypass-pre-merge-gates]

- [ ] 1.2 Update the Phase 1b comment to reflect the corrected understanding: `status=integrating` is set at the START of the verify pipeline (by `_integrate_main_into_branch`), so recovery must distinguish "gates passed, merge_queue append lost" from "pipeline interrupted mid-gate".
  [REQ: orphan-cleanup/phase-1b-must-not-bypass-pre-merge-gates]

## 2. Tests

- [ ] 2.1 Update `tests/unit/test_orphan_cleanup.py::TestRestoreOrphanedIntegrating::test_integrating_with_worktree_gets_requeued`: rename to `test_integrating_with_gates_passed_gets_requeued`, populate all 6 gate-result fields (`build_result`, `test_result`, `review_result`, `scope_check`, `e2e_result`, `spec_coverage_result`) with `"pass"`. Assert change is in `merge_queue` and `status` remains `integrating`.
  [REQ: orphan-cleanup/phase-1b-must-not-bypass-pre-merge-gates]

- [ ] 2.2 Add `test_integrating_with_gates_incomplete_resets_to_running`: only some gate results set (e.g., `build_result="pass"`, rest None). Assert `status=="running"`, `ralph_pid is None`, change NOT in `merge_queue`.
  [REQ: orphan-cleanup/phase-1b-must-not-bypass-pre-merge-gates]

- [ ] 2.3 Add `test_integrating_with_spec_verify_fail_resets_to_running`: all gates pass EXCEPT `spec_coverage_result="fail"`. Assert `status=="running"`, change NOT in `merge_queue`.
  [REQ: orphan-cleanup/phase-1b-must-not-bypass-pre-merge-gates]

- [ ] 2.4 Add `test_integrating_with_review_fail_resets_to_running`: all gates pass EXCEPT `review_result="fail"`. Assert `status=="running"`, change NOT in `merge_queue`.
  [REQ: orphan-cleanup/phase-1b-must-not-bypass-pre-merge-gates]

- [ ] 2.5 Keep `test_integrating_already_in_queue_untouched`, `test_integrating_without_worktree_not_requeued`, `test_non_integrating_not_requeued` as-is (preconditions they test are orthogonal to the gate check).

- [ ] 2.6 Run `pytest tests/unit/test_orphan_cleanup.py -v` — all tests pass.

## 3. Verify

- [ ] 3.1 Run `pytest tests/unit/` to confirm no other tests regressed.
- [ ] 3.2 Grep for other places that might rely on the old "always requeue integrating" behavior. None expected, but verify.
