## 1. Replan Gate

- [x] 1.1 Add `_all_coverage_merged()` helper in `lib/set_orch/engine.py` that checks coverage.json — returns True if all requirements have status "merged" or "planned" with a corresponding merged change [REQ: replan-gate/REQ-1]
- [x] 1.2 Add coverage-based gate before `_handle_auto_replan` call: if `truly_complete == total && failed_count == 0 && _all_coverage_merged()` → skip replan, go to done [REQ: replan-gate/REQ-1]
- [x] 1.3 Change "batch_complete" handling in `_auto_replan_cycle`: instead of full Phase 2+3 re-decompose, check coverage and use "coverage_gap" trigger if gaps exist, otherwise return "no_new_work" [REQ: replan-gate/REQ-4]

## 2. No-Op Detection

- [x] 2.1 Add `_is_no_op_change()` helper in `lib/set_orch/merger.py` that checks `git rev-list --count {merge_base}..HEAD` in worktree — returns True if 0 new commits [REQ: no-op-detection/REQ-1]
- [x] 2.2 In `execute_merge_queue`, before `_run_integration_gates`: if `_is_no_op_change()` → skip gates, log warning, proceed to merge [REQ: no-op-detection/REQ-2, REQ-3, REQ-4]
