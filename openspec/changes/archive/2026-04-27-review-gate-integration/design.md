# Design: Review Gate Integration

## Current Flow (broken)

```
engine._poll_active_changes()
  → detects loop_status=done
  → engine marks status="done" directly (L1019)
  → WARNING: "orphaned done change" (L1039)
  → adds to merge_queue
  → merger._run_integration_gates() (build/test/e2e only)
  → merge_change()
```

The verifier pipeline is never entered.

## New Flow

```
engine._poll_active_changes()
  → detects loop_status=done
  → calls handle_change_done() from verifier (with all kwargs)
  → verifier GatePipeline runs:
      build → test → e2e → scope → test_files → coverage → REVIEW → rules → spec_verify
  → if all pass: status="done", add to merge_queue
  → if retry: resume_change() (agent fixes review findings)
  → if fail: status="verify-failed"
  → merger._run_integration_gates() still runs (post-integration validation)
  → merge_change()
```

## Changes

### 1. engine.py — Route done changes through verifier

In `_poll_active_changes()` (L978), when `ralph_status == "done"` is detected in verifier's `poll_change()`, it already calls `handle_change_done()` (verifier.py:1932). The problem is the engine ALSO has its own done detection at L1019 that runs BEFORE `poll_change()`.

**Fix:** Remove the engine's direct done→merge shortcut. Let `poll_change()` handle the "done" detection, which already calls `handle_change_done()`.

The key issue: engine.py L1019 checks change.status == "done" and adds to merge queue. But this runs on EVERY poll cycle. The verifier's `handle_change_done` sets status to "done" and adds to merge queue AFTER gates pass. The engine then picks this up next poll and tries to add to merge queue AGAIN.

**Actual fix:** The engine's "orphaned done" handler (L1039) needs to NOT add to merge queue if the change was just set to "done" by the verifier — it should only handle truly orphaned done changes (e.g., from manual state edits). Add a field like `gates_passed: true` that handle_change_done sets after pipeline success.

### 2. verifier.py — Ensure handle_change_done is called

The `poll_change()` function (L1809) already calls `handle_change_done()` when ralph_status == "done" (L1932). This is correct. The issue is that the engine's own done detection at L1019 pre-empts this.

**Fix:** In engine.py `_poll_active_changes`, when a change's loop-state shows status="done", let it flow through to `poll_change()` which handles it correctly. Remove the engine's direct status="done" assignment for this case.

### 3. No changes needed in:
- merger.py (integration gates stay)
- gate_runner.py (pipeline framework stays)
- gate_profiles.py (config stays)
- verifier.py review gate implementation (stays)

## Edge Cases

1. **Agent crashes with status=done in loop-state but no gate pipeline ran**: The verifier's `poll_change` handles this — it reads loop-state, sees "done", calls `handle_change_done`.

2. **Double merge queue add**: The verifier adds to merge queue after gates pass. The engine's orphan handler must not re-add. Guard with `gates_passed` field or check if already in merge_queue.

3. **Retry loop**: If review finds CRITICAL issues, verifier dispatches agent to fix. Agent runs again, finishes, `poll_change` detects done again, runs gates again. This is the intended flow.
