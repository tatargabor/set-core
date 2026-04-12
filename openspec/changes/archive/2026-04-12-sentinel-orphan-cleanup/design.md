# Design: sentinel-orphan-cleanup

## Context

The orchestrator runs as a long-lived process that spawns agent sessions (ralph loops) in worktrees. When the orchestrator crashes or the sentinel restarts, these resources can be left in inconsistent states:
- Worktrees exist on disk but the orchestrator no longer tracks them
- `ralph_pid` references dead processes, causing dashboard animations to freeze
- `current_step` stuck at intermediate values (`integrating`, `merging`)

Real example from craftbrew-run22:
- `checkout-flow-2`: worktree existed, not in state, no process — took disk space
- `checkout-flow`: `ralph_pid=2453666` (dead), `step=integrating` — dashboard M gate animated forever

## Goals / Non-Goals

**Goals:**
- Clean orphaned worktrees on orchestrator startup (before poll loop)
- Fix stale PIDs and stuck steps automatically
- Conservative: never destroy potentially useful state

**Non-Goals:**
- Killing orphaned processes (too dangerous — could be user sessions or useful work)
- Real-time monitoring during poll loop (startup-only is sufficient)
- Cross-project cleanup (only clean current project's worktrees)

## Decisions

### D1: Startup-only, not continuous

**Choice:** Run cleanup once at `monitor_loop()` entry, before the first poll.

**Why:** Orphans only appear after restarts. Running cleanup every poll cycle wastes time and risks race conditions with active dispatches. Once at startup is sufficient.

### D2: Never kill processes

**Choice:** If a worktree has a running process (checked via lsof or /proc), skip it entirely.

**Why:** The process might be:
- A user manually working in the worktree (`claude -p` in that dir)
- An agent session that outlived the sentinel but is still doing useful work (committing final changes)
- A gate runner (playwright, vitest) mid-execution

Killing any of these would destroy work. The safe action is to log and skip. The worktree will be cleaned on the next restart if the process is gone.

### D3: Dirty worktree = skip

**Choice:** If `git status --porcelain` returns non-empty, don't remove the worktree.

**Why:** Uncommitted changes might be:
- Agent work that wasn't committed before crash (valuable code that could be recovered)
- User edits in progress

Removing would destroy work. Log the warning, let the user decide.

### D4: Running change + dead PID = stalled (not pending)

**Choice:** When a `running` change has a dead ralph_pid, set status to `stalled` instead of `pending`.

**Why:** The stall recovery path (in the monitor loop) handles redispatch with retry context. Setting to `pending` would lose the retry context and any iteration count. `stalled` is the correct status for "agent died mid-work."

### D5: Use locked_state for all modifications

**Choice:** All state modifications in cleanup go through `locked_state()` context manager.

**Why:** The sentinel or manager might be reading state concurrently. Atomic writes prevent corruption.

## Risks / Trade-offs

- **[Risk] Race with dispatch** — Cleanup runs before poll loop starts, but dispatch might happen during a health_check restart. Mitigation: cleanup only touches merged/done changes and orphaned worktrees — never active ones.
- **[Risk] Worktree removal fails** — `git worktree remove --force` can fail if the worktree is a git submodule or has locks. Mitigation: catch exceptions, log warning, continue.
- **[Risk] False orphan detection** — A worktree might be created by the user for manual work. Mitigation: only consider worktrees matching the `<project>-wt-*` naming pattern.
