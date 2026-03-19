# Proposal: Orchestrator Resume Mode

## Problem

Three independent issues prevent clean mid-run restart:

1. **Sentinel nukes state**: when `status=done/stopped` with no failed worktrees, sentinel deletes `orchestration-state.json`, `orchestration-plan.json`, events, and worktrees
2. **`wt-orchestrate start` always re-plans**: if plan file is missing (because sentinel deleted it), triggers full digest + decompose (~5-10 min)
3. **No lightweight resume**: the only way to restart the monitor is through `cmd_start` which runs the full init pipeline

Real impact: after deploying a wt-tools fix mid-run, restarting takes 5-10 min (unnecessary decompose) or loses state entirely (sentinel fresh start).

## Solution

Add `wt-orchestrate start --resume` (or detect automatically) that:
1. Requires existing state file — errors if missing
2. Skips digest, planning, and state re-initialization entirely
3. Detects crashed/zombie processes and marks them stalled
4. Goes directly to the Python monitor loop

Also fix sentinel state protection: don't delete state on `done`/`stopped` — back it up instead.

## Scope

### In Scope
- `--resume` flag on `wt-orchestrate start` (skip planning, use existing state)
- Auto-detect resume: if state file exists with running/pending changes, skip planning
- Sentinel: backup state instead of deleting on done/stopped
- `wt-orchestrate resume` alias (same as `start --resume`)

### Out of Scope
- Changing the planning pipeline itself
- Hot-reload of Python modules (would require importlib complexity)
- Sentinel auto-restart with resume mode (future)
