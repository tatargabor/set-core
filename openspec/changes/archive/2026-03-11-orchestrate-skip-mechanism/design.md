## Context

The wt-orchestrate pipeline processes changes in dependency order. When a change fails (implementation issues, budget exhaustion, spec problems), it becomes a terminal state — but `deps_satisfied()` only accepts `"merged"` as a satisfying status. This means any change downstream of a failure is permanently blocked, even if the failed change was a leaf or non-critical feature.

Currently the operator's only options are: fix the failing change, manually edit the state JSON, or restart the entire orchestration. A clean skip mechanism is needed.

Key files:
- `lib/orchestration/state.sh` — `deps_satisfied()` (line 160), `deps_failed()` (line 181), `cascade_failed_deps()` (line 202)
- `lib/orchestration/monitor.sh` — completion check (lines 320-344)
- `lib/orchestration/reporter.sh` — CSS classes (lines 49-57), status rendering
- `bin/wt-orchestrate` — subcommand dispatch (lines 605-636)

## Goals / Non-Goals

**Goals:**
- Allow operator to skip a failed/pending/stalled change and unblock the pipeline
- Preserve full auditability — skipped is distinct from merged and failed
- Minimal changes — reuse existing patterns (status field, CLI dispatch, CSS classes)

**Non-Goals:**
- Auto-skip logic (always manual operator decision)
- Skip with partial merge (change is fully skipped, no code lands)
- Undo/unskip (operator can manually edit state if needed)

## Decisions

### D1: "skipped" as a new terminal status value
Store `"skipped"` in the change's `status` field in the state JSON, same as `"merged"` or `"failed"`. This is the simplest approach — no new data structures, all existing status queries work with minor additions.

Alternative considered: separate `skip` boolean flag alongside status. Rejected because it complicates every status check and the status field already models lifecycle states.

### D2: deps_satisfied() accepts "merged" OR "skipped"
Change the check from `!= "merged"` to `!= "merged" && != "skipped"`. This is the minimal change to unblock downstream changes.

`deps_failed()` should NOT treat skipped as failed — skipped is an explicit operator decision, not a failure. This prevents cascade_failed_deps from propagating skip as failure.

### D3: Skip metadata in state JSON
When skipping, store `skip_reason` (optional operator-provided text) and `skipped_at` (ISO timestamp) on the change object. This provides audit trail without adding complexity.

### D4: CLI command structure
`wt-orchestrate skip <name> [--reason "text"]` — follows existing pattern of `cmd_pause`, `cmd_resume`. Validates that the change exists and is in a skippable status (failed, pending, stalled, merge-blocked, build-blocked, verify-failed). Refuses to skip running/verifying changes (must pause first).

### D5: Reporter amber styling
Use `#ff9800` (amber/orange — same as running) would be confusing. Use `#ffc107` (distinct amber/yellow) for `.status-skipped`. Summary row shows skipped count separately: "3 merged, 1 skipped, 1 failed".

## Risks / Trade-offs

- [Risk] Skipping a change that has important side effects for downstream changes → Mitigation: This is an operator decision with explicit `--reason` flag for documentation. The reporter clearly shows skipped status.
- [Risk] Replan may try to re-schedule skipped changes → Mitigation: Replan reads the state file and should treat skipped as terminal. No special handling needed since replan already skips non-pending changes.
- [Trade-off] No undo mechanism → Acceptable for v1. Manual state edit is possible if needed.
