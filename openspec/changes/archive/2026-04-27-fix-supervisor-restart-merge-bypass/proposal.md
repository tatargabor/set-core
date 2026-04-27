# Change: fix-supervisor-restart-merge-bypass

## Why

A supervisor restart during an in-flight verify pipeline can cause a change to be merged even when its pre-merge gates (spec_verify, review, rules) fail. Observed in craftbrew-run-20260414-0140 promotions-and-email: `VERIFY_GATE result=retry stop_gate=spec_verify spec_verify=fail` at 21:11:20, integration gates running at 21:11:20 simultaneously, MERGE_SUCCESS at 21:12:28. Final state has `spec_coverage_result=fail` AND `status=merged` — a direct verdict-bypass.

### Root cause

`_cleanup_orphans` at `engine.py:389-415` (Phase 1b) restores changes with `status=integrating` to the merge queue on orchestrator startup:

```python
for change in st.changes:
    if change.status != "integrating":
        continue
    if change.name in st.merge_queue:
        continue
    wt = change.worktree_path or ""
    if not wt or not os.path.isdir(wt):
        continue
    st.merge_queue.append(change.name)  # ← no gate check
```

The comment claims this recovers from "sentinel dying mid-merge". But `status=integrating` is written in exactly one place: `verifier.py:3313` `_integrate_main_into_branch`, which runs at the START of the verify pipeline, BEFORE gates execute. The merger never sets this status. Therefore Phase 1b always triggers on "died mid-verify" cases, not "died mid-merge" as the comment assumes.

After a mid-verify restart:
1. Phase 1b appends the change to `merge_queue` unconditionally.
2. The new supervisor instance re-runs the verify pipeline via `poll_change` → `handle_change_done`.
3. The pipeline fails (e.g., spec_verify reports CRITICAL findings) → `status=verify-failed`, retry dispatched.
4. `resume_change` does NOT remove the change from `merge_queue`.
5. The next main-loop cycle runs `_drain_merge_then_dispatch`, sees the change in `merge_queue`, and executes the merger.
6. The merger runs only integration gates (dep_install, build, test, e2e) — it has no visibility into spec_verify/review/rules results, so it merges.

The fix must be narrow: restore the invariant that changes reach the merger only through the verify-passes path (`verifier.py:3819-3827`) or an equivalent guarded recovery.

### Design constraint: restart is not a failure

Supervisor crashes are infrastructure events, not agent or code faults. A restart mid-gate must re-run the verify pipeline without consuming a `verify_retry_count` slot — same semantic as a pass-through. Using `status=verify-failed` would route through `_recover_verify_failed` which respects the retry limit and could prematurely fail a change whose previous attempt was genuinely its last one.

The agent's `loop-state.json` is still `status=done` on disk (it was written when the agent finished, before the verify pipeline started). Setting `change.status=running` and clearing `ralph_pid` causes `_poll_active_changes` (engine.py:1135-1160) to detect "dead agent with `loop_status=done`" and route the change back through `handle_change_done`. No retry counter mutation, full gate re-execution.

## What Changes

### engine.py `_cleanup_orphans` Phase 1b (engine.py:389-415)

Replace unconditional `merge_queue.append` with a gate-aware branch:

1. If `_verify_gates_already_passed(change)` is True → safe to merge, add to `merge_queue` (existing behavior).
2. Otherwise → reset `status=running`, clear `ralph_pid`, do NOT add to `merge_queue`. The next poll cycle's `_poll_active_changes` will detect the dead agent + `loop_status=done` and re-enter `handle_change_done`, which re-runs the full verify pipeline.

### Tests

Update `tests/unit/test_orphan_cleanup.py::TestRestoreOrphanedIntegrating` to reflect the new semantics:

- `test_integrating_with_gates_passed_gets_requeued` — all gate results present and pass → `merge_queue` (unchanged behavior).
- `test_integrating_with_gates_incomplete_resets_to_running` — NEW: some gates None → `status=running`, `ralph_pid=None`, NOT in `merge_queue`.
- `test_integrating_with_spec_verify_fail_resets_to_running` — NEW: `spec_coverage_result=fail` → `status=running`, NOT in `merge_queue`.
- `test_integrating_already_in_queue_untouched` — keep (guards against duplication).
- `test_integrating_without_worktree_not_requeued` — keep.
- `test_non_integrating_not_requeued` — keep.

## Out of scope

- The secondary gap that `_verify_gates_already_passed` checks only 6 of ~10 registered gates (missing `rules_result`, `e2e_coverage_result`, `lint_result`, `test_files`, `smoke_e2e_result`). Tracked separately.
- Renaming `status=integrating` for semantic clarity (the verifier's "integrate main" step vs. the merger's "integrate" phase share a name). Out of scope — would touch many call sites.
- Merger-level pre-merge gate re-check (would eliminate the bypass at a second layer, complementary to this fix).
