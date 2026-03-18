# Design: Graceful Shutdown

## Context

The sentinel process tree is: `wt-sentinel` → `wt-orchestrate` → Python monitor → `wt-loop` (per change). Currently, SIGTERM/SIGINT causes immediate cascade kill — the orchestrator's atexit sets status to `"stopped"`, but agents are killed mid-work. The sentinel's `fix_stale_state()` can recover from crashes, but there's no orderly shutdown that preserves agent progress.

The existing signal flow:
- Sentinel traps SIGINT/SIGTERM → sends SIGTERM to orchestrator child → exits
- Orchestrator atexit → sets state `"stopped"`, kills dev server
- Agents (wt-loop) → killed by signal propagation, no cleanup

## Goals / Non-Goals

**Goals:**
- Orderly shutdown that lets agents commit WIP before exiting
- Resume from shutdown without re-dispatching completed work
- E2E test projects in persistent directories

**Non-Goals:**
- Cross-machine state migration
- Auto-save/checkpoint during normal operation (existing checkpoint mechanism handles this)

## Decisions

### 1. Shutdown trigger: `--shutdown` flag on sentinel

The `--shutdown` flag sends SIGUSR1 to the running sentinel (found via PID file). The sentinel then orchestrates the shutdown sequence.

**Alternative considered:** New `wt-shutdown` binary. Rejected — adds a new entry point for a single-use operation. The sentinel already manages the process tree.

**Alternative considered:** Signal the orchestrator directly. Rejected — sentinel owns the process tree and cleanup; bypassing it would leave the sentinel in an inconsistent state.

### 2. Agent stop: SIGTERM + `stop_requested` flag in wt-loop

wt-loop traps SIGTERM and sets `stop_requested=true`. After the current Claude session exits naturally, wt-loop checks the flag, commits WIP, and exits.

The Claude CLI process is NOT killed — it completes its current turn. This avoids corrupted state from mid-tool-call interruption.

**Timeout:** If the Claude session doesn't exit within 60 seconds after SIGTERM, the loop force-kills it and commits whatever is on disk.

### 3. State status: `"shutdown"` (distinct from `"stopped"`)

A new status `"shutdown"` distinguishes intentional shutdown from crash. This lets the sentinel's resume logic know that worktrees were preserved intentionally and should be validated rather than cleaned up.

`"stopped"` (crash) → `fix_stale_state()` → clean worktrees, re-dispatch
`"shutdown"` (intentional) → validate worktrees → resume in-place

### 4. Resume validation: branch HEAD comparison

At resume time, the sentinel checks each running change's worktree:
1. Directory exists? → if not, reset to pending
2. Branch HEAD matches `last_commit`? → if not, log warning, reset to pending
3. Both valid? → re-dispatch with `--resume` flag (skip artifact creation, continue from last task)

This handles the case where someone manually modified the worktree between shutdown and resume.

### 5. E2E project directory: `--project-dir` flag

Simple flag on `run.sh` / `run-complex.sh`. Default remains `/tmp/` for backward compatibility. The flag just changes the base directory variable — no other logic changes needed.

## Risks / Trade-offs

- **[Risk] Claude session may take 5+ minutes to complete** → 60s timeout with SIGKILL fallback. Stalled changes get re-dispatched on resume.
- **[Risk] Worktree disk space not freed on shutdown** → Intentional: worktrees are needed for resume. Document that `wt-sentinel --cleanup` (existing) removes them.
- **[Risk] PID file stale after reboot** → Already handled by existing `fix_stale_state()`. Shutdown writes `shutdown_at` as additional signal.

### 6. wt-web integration: API endpoint + Settings UI

**API:** New `POST /api/{project}/shutdown` endpoint in `lib/wt_orch/api.py`. Follows the same pattern as existing `/api/{project}/stop` — reads sentinel PID file, sends SIGUSR1, returns JSON. Distinct from `/stop` because `/stop` kills the orchestrator immediately while `/shutdown` triggers the graceful sequence.

**Settings page:** `web/src/pages/Settings.tsx` gains an "Orchestration Control" section with:
- **Shutdown button** (red, destructive styling) → confirmation dialog → calls shutdown API → shows spinner
- **Resume button** (green, shown when status is `"shutdown"`) → calls existing start endpoint
- **Status badge** reflecting current state (`running`, `shutdown`, `stopped`)

**Pattern:** Follows existing `StatusHeader.tsx` button pattern (loading state, disabled while in-flight, try/catch).

## Open Questions

- Should `--shutdown` wait for the current merge queue to flush, or stop immediately? (Recommendation: stop immediately — merges can resume)
