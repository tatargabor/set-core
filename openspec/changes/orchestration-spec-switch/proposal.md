# Proposal: Orchestration Spec Switch

## Why

When an orchestration run completes and the user wants to run a new spec on the same project (e.g., gap-fix spec after initial v1 run), there's no clean way to do it. The current options are all manual hacks or destructive resets. The sentinel should handle this automatically.

## What Changes

### 1. Reuse existing `brief_hash` / `input_path` for spec tracking

The state model already has `brief_hash` (in `OrchestratorState`, `lib/set_orch/state.py`) and `input_path` is tracked in the bash state layer (`lib/orchestration/state.sh`). The `cmd_status` function in `set-orchestrate` already warns "Input has changed since plan was created" when the hash differs.

**Reuse this infrastructure** — no new `spec_source`/`spec_hash` fields needed. The sentinel computes `brief_hash <spec_path>` (already in `lib/orchestration/utils.sh`) and compares against `.brief_hash` in the state file.

### 2. Auto-reset on spec change (in sentinel bash layer)

When sentinel detects a spec change, it performs an orchestration reset **inside the flock guard**, after `fix_stale_state` but before launching the orchestrator:

```
Sentinel startup (inside flock):
  1. Read orchestration-state.json → get brief_hash, input_path
  2. Compute brief_hash of --spec argument
  3. If SAME → resume (current behavior)
  4. If DIFFERENT:
     a. Log: "Spec changed: docs/v1.md → docs/v1-gaps.md — resetting orchestration"
     b. Delete orch/* tags from prior completed run (so cleanup isn't blocked)
     c. Call clean_old_worktrees() — now unblocked by tag removal
     d. Only delete branches that are merged to main (git branch --merged main)
     e. Remove: orchestration-state.json, events.jsonl, digest/, lock files
     f. Do NOT touch main branch or git history
     g. Start fresh orchestration with new spec
```

**Critical**: This logic runs in `set-sentinel` (bash), NOT in the Python engine. The sentinel handles cleanup before invoking `set-orchestrate start`. The Python engine only writes `brief_hash` to state on init.

### 3. `orch/*` tag handling

`clean_old_worktrees()` has a guard: if `orch/*` tags exist, it skips cleanup. This guard protects history for runs in progress, but blocks cleanup for completed runs when switching specs.

**Fix**: When spec-switch is detected, delete `orch/*` tags from the prior run before calling `clean_old_worktrees()`. This is safe because the prior run is complete — the tags served their purpose.

### 4. Safe branch cleanup

Only delete `change/*` branches that are **merged to main**:
```bash
git branch --merged main | grep 'change/' | xargs git branch -d
```

Unmerged branches (from partial runs) are preserved — the user may want to salvage work from them.

### 5. `--fresh` flag

For re-running the same spec with identical content:
```bash
set-sentinel --spec docs/v1.md --fresh
```

Forces orchestration reset even when `brief_hash` matches. Covers the case where the user wants a clean restart without modifying the spec file. This is the only case where `--fresh` is needed — content changes on the same path are caught by hash comparison.

## Where the changes go

All spec-switch logic lives in `set-sentinel` (bash layer):

| Component | File | Change |
|-----------|------|--------|
| Sentinel | `bin/set-sentinel` | Spec hash comparison inside flock, auto-reset flow, `--fresh` flag |
| Sentinel | `bin/set-sentinel` | `clean_old_worktrees()`: handle `orch/*` tag deletion on spec-switch |
| State init | `lib/orchestration/state.sh` | Ensure `brief_hash` + `input_path` written on fresh start |
| Python state | `lib/set_orch/state.py` | Ensure `brief_hash` preserved on Python state writes |

**NOT in Python engine** — the engine doesn't need spec-switch awareness. It receives a clean state from the sentinel.

## Risk

**Low**. The auto-reset is a superset of what users currently do manually.

| Risk | Mitigation |
|------|-----------|
| Accidental reset on trivial spec edit | Hash-based comparison is content-aware; log message warns user |
| Unmerged work lost | Only delete `--merged` branches; unmerged preserved |
| `orch/*` tags deleted prematurely | Only deleted when spec-switch detected, not on resume |
| Race condition on startup | Logic runs inside flock guard |

## Scope

### In Scope
- Spec hash comparison on sentinel startup (reusing `brief_hash`)
- Auto-reset on spec change (state, events, digest, worktrees, locks)
- Safe branch cleanup (merged-only)
- `orch/*` tag cleanup on spec-switch
- `--fresh` flag for forced reset
- Clear logging

### Out of Scope
- Incremental spec changes mid-run
- Merging state from two different specs
- Run history tracking
- `set-orchestrate reset --spec-change` CLI mode (unnecessary — sentinel handles it)
