## Context

During a long-running orchestration, the orchestrator entered checkpoint state (waiting for user approval via wt-web). The sentinel's stuck detection saw no events for 180s and killed the orchestrator. After restart, the sentinel did a partial reset (failed→pending, preserve worktrees). The merge pipeline re-ran for remaining changes but coverage.json was not updated — requirements stayed "planned" despite their changes being merged. The auto-replan saw all changes as merged and declared "done" without noticing the coverage gap.

Three independent bugs combine to cause this:
1. Sentinel kills orchestrator during legitimate checkpoint wait
2. Coverage not synced after partial-reset merges
3. Completion check ignores coverage state

## Goals / Non-Goals

**Goals:**
- Sentinel respects checkpoint state with a bounded maximum wait
- Coverage.json always reflects actual merge status
- Completion check validates coverage before declaring done

**Non-Goals:**
- Changing checkpoint_every or merge_policy defaults
- Auto-approving checkpoints (user already has `checkpoint_auto_approve` directive)
- Reworking the partial reset mechanism itself

## Decisions

### 1. Sentinel: checkpoint-aware stuck detection with bounded wait

**Decision:** In `check_orchestrator_liveness()`, read the state file and skip stuck detection when `status == "checkpoint"`, but enforce a `CHECKPOINT_MAX_WAIT` (default: 86400s / 24h) to prevent unbounded waits.

**Why:** The orchestrator is alive and looping during checkpoint — it's just not producing events because `continue` skips dispatch/merge. This is expected behavior, not a hang. But a completely unbounded wait is dangerous — if the user abandons the session, the sentinel should eventually stop.

**Alternative considered:** Have the orchestrator emit periodic heartbeat events during checkpoint. Rejected — adds complexity to the engine for something that's simpler to fix in the sentinel.

**Implementation:** In `bin/wt-sentinel`, modify `check_orchestrator_liveness()`:
```bash
# Skip stuck detection during checkpoint — orchestrator is alive but waiting
if [[ -f "$STATE_FILE" ]]; then
    local current_status
    current_status=$(jq -r '.status // ""' "$STATE_FILE" 2>/dev/null) || return 0
    # ↑ On jq parse failure (torn read), fail safe by skipping the kill
    if [[ "$current_status" == "checkpoint" ]]; then
        # Bound the wait — don't wait forever if user abandons
        local cp_started
        cp_started=$(jq -r '.checkpoint_started_at // 0' "$STATE_FILE" 2>/dev/null || echo 0)
        local cp_age=$(( $(date +%s) - cp_started ))
        if [[ "$cp_age" -ge "$CHECKPOINT_MAX_WAIT" ]]; then
            sentinel_log "Checkpoint wait exceeded ${CHECKPOINT_MAX_WAIT}s — stopping"
            return 1
        fi
        return 0  # not stuck, waiting for approval
    fi
fi
```

**Edge cases:**
- **State file unreadable (torn read):** `jq` failure triggers `|| return 0`, skipping the kill. This is the safe direction — better to skip a kill than to false-positive kill during checkpoint.
- **Orchestrator dies during checkpoint:** `fix_stale_state()` preserves checkpoint status (existing behavior), sentinel restarts orchestrator. Running changes get marked stalled by `fix_stale_state()` — the resumed orchestrator handles stalled changes in checkpoint processing.

### 2. Coverage reconciliation after restart

**Decision:** Add `reconcile_coverage()` to `digest.py` that syncs coverage.json with actual state. Call it from `_check_completion()` before any terminal decision.

**Why:** The current `update_coverage_status()` is called from `merge_change()` (merger.py:342-343). But after a sentinel restart + partial reset, some changes may already be "merged" in state without going through the full merge pipeline (they were merged in a previous orchestrator instance). Coverage.json still shows them as non-merged.

**Implementation:** New function in `digest.py`:
```python
def reconcile_coverage(state_file: str, digest_dir: str = DIGEST_DIR) -> int:
    """Sync coverage.json with actual change statuses from state.

    For each requirement in coverage.json, if its change is 'merged' in state
    but coverage status is anything other than 'merged', update it.
    Uses cov_data.get("coverage", {}) to unwrap the nested structure.
    Writes to coverage-merged.json via read-merge-write (same pattern
    as update_coverage_status()).

    Returns number of requirements fixed.
    """
```

**Key implementation details:**
- Unwrap coverage with `cov_data.get("coverage", {})` — same pattern as `update_coverage_status()` and `check_coverage_gaps()`
- Check `entry.get("status") != "merged"` (not just `== "planned"`) — handles any non-merged status including hypothetical "dispatched"
- Write to coverage-merged.json via read-merge-write, not file append
- Return 0 and no error if coverage.json doesn't exist (no-digest mode)

### 3. Completion check validates coverage — placement before all exit paths

**Decision:** In `_check_completion()`, call `reconcile_coverage()` after the early-return guard (after the "not all resolved" check) but before any of the three terminal branches (dep_blocked, total_failure, normal done/replan). This ensures coverage is reconciled regardless of which exit path is taken.

**Why:** Making coverage a hard gate would risk blocking legitimate completions if the digest has edge cases. The reconciliation approach is defensive — fix the data, log the fix, proceed.

**Concurrency safety:** The safety guarantee depends on the single-threaded Python event loop — `_retry_merge_queue_safe()` completes synchronously before `_check_completion()` runs. No concurrent merges are possible at the call site.

## Risks / Trade-offs

- **[Risk] State file torn read in sentinel** → Mitigation: `jq` failure triggers `|| return 0` (fail safe — skip the kill).
- **[Risk] reconcile_coverage races with merge_change** → Mitigation: Only called from `_check_completion()` after all changes are terminal. Single-threaded loop guarantees no concurrent merges. If loop is ever parallelised, this must be revisited.
- **[Risk] Coverage reconciliation masks real bugs** → Mitigation: Logs every fix at WARNING level so it's visible in orchestration.log. The root cause (sentinel killing during checkpoint) is also fixed.
- **[Risk] Unbounded checkpoint wait** → Mitigation: `CHECKPOINT_MAX_WAIT` (24h default) bounds the wait. Sentinel stops with a clear log message.
