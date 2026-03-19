## Context

Phase 5 of the Python migration. `dispatcher.sh` (1438 LOC) is the change lifecycle engine: it creates worktrees, bootstraps environments, dispatches agents via wt-loop, manages pause/resume/stall/recovery, and runs the orchestrator's `cmd_start`/`cmd_pause`/`cmd_resume` entry points.

Existing Python modules already cover the dependencies:
- `state.py` — state read/write, locking, deps, topo sort
- `events.py` — event bus (emit/query)
- `process.py` — PID check, safe-kill, orphan scan
- `config.py` — directive parsing, resolve, find_input
- `templates.py` — proposal/review/fix/planning templates
- `planner.py` — validate, enrich, decompose context

The dispatcher heavily calls these plus external CLIs (`git`, `wt-new`, `wt-loop`, `openspec`).

## Goals / Non-Goals

**Goals:**
- 1:1 function mapping from bash to Python with source line references in comments
- All 17 functions migrated to `lib/set_orch/dispatcher.py`
- CLI subcommands in `set-orch-core dispatch *` for bash bridge
- `dispatcher.sh` reduced to thin wrappers (~50 LOC) calling `set-orch-core`
- Structured logging via `logging.getLogger(__name__)`
- Type hints on all functions, dataclasses for structured returns
- pytest tests per capability group

**Non-Goals:**
- Changing dispatcher behavior or logic (pure migration)
- Migrating `monitor_loop` (that's phase 7: monitor.sh)
- Migrating the `wt-loop` startup mechanism itself (phase 8)
- Adding new features to dispatch logic

## Decisions

### 1. Module structure: single `dispatcher.py` file
**Rationale**: The 17 functions have tight coupling (shared state access, git operations, worktree paths). Splitting into 4 files would create circular imports or excessive parameter passing. A single 800-1000 line module with clear section headers mirrors the bash structure.
**Alternative**: 4 modules (worktree.py, routing.py, lifecycle.py, recovery.py) — rejected due to tight coupling between dispatch/resume and recovery paths.

### 2. Git operations via `subprocess_utils.run_cmd`
**Rationale**: Git operations (sync, merge, branch management) are inherently shell commands. Using `subprocess_utils.run_cmd()` (from phase 1) provides structured error handling, timeout, and logging. No benefit from a git library (gitpython adds deps, pygit2 is complex).
**Alternative**: `gitpython` library — rejected, adds dependency for marginal benefit.

### 3. State access via `set_orch.state` module directly (not CLI bridge)
**Rationale**: dispatcher.py lives in the same Python package as state.py. Direct function calls are faster and type-safe vs. shelling out to `set-orch-core state *`. The CLI bridge is only for bash→Python interop.
**Alternative**: CLI bridge for all state access — rejected, unnecessary indirection within Python.

### 4. Bash wrapper pattern: same as phases 3-4
**Rationale**: `dispatcher.sh` functions become one-liner calls to `set-orch-core dispatch <subcmd>`. This allows gradual migration — bash callers (monitor.sh, engine.sh) keep working without changes.

### 5. `cmd_start` stays in bash initially
**Rationale**: `cmd_start` is 370 lines orchestrating plan→state→dispatch→monitor_loop sequence, deeply integrated with bash trap handlers and the monitor loop. Migrating the full cmd_start requires monitor_loop (phase 7). For phase 5, we migrate the _dispatch-related_ helpers that cmd_start calls, but cmd_start itself remains in bash calling the new Python functions via CLI bridge.

## Risks / Trade-offs

- **[Risk] subprocess calls to git may fail differently than bash** → Mitigation: `subprocess_utils.run_cmd` captures stderr, returns structured result. Tests cover error paths.
- **[Risk] wt-loop startup race condition** → Mitigation: Preserve existing poll-for-loop-state.json pattern with configurable timeout.
- **[Risk] Signal handling in cmd_start trap** → Mitigation: cmd_start stays in bash for phase 5; signal trap migration deferred to phase 7.
- **[Risk] State file locking contention** → Mitigation: Use existing `locked_state` context manager from state.py for all state mutations.
