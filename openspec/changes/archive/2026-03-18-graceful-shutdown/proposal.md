# Proposal: Graceful Shutdown

## Why

The sentinel/orchestrator cannot survive a machine reboot or intentional shutdown. Agent processes are killed without cleanup, worktree state becomes stale, and if the project directory is in a volatile location (e.g., `/tmp/`), all progress is lost. Users running multi-hour orchestration runs need the ability to gracefully stop, preserve state, and resume later — even after a full system restart.

## What Changes

- **New**: `wt-sentinel --shutdown` command that performs graceful shutdown: signals agents to finish current task, waits for clean exit, saves resume metadata, and stops the sentinel
- **New**: Resume-on-start logic in sentinel that detects incomplete runs and offers to continue from saved state
- **New**: Agent-level graceful stop — `wt-loop` handles SIGTERM by completing current iteration before exiting, committing work-in-progress
- **Modified**: Sentinel signal handling — SIGTERM triggers graceful shutdown sequence instead of immediate kill
- **Modified**: State file gains `shutdown_at` timestamp and per-change `last_commit` fields for resume validation
- **Modified**: E2E scaffold scripts gain `--project-dir` flag to allow persistent (non-`/tmp/`) project directories
- **New**: wt-web Settings menu "Shutdown" button with confirmation dialog, status indicator, and resume action
- **New**: API endpoint `POST /api/{project}/shutdown` that triggers `wt-sentinel --shutdown`

## Capabilities

### New Capabilities
- `graceful-shutdown` — Orderly shutdown and resume of orchestration runs across process restarts

### Modified Capabilities
- (none — existing specs don't cover shutdown/resume lifecycle)

## Impact

- **Sentinel**: `bin/wt-sentinel` — new `--shutdown` flag, modified signal handlers, resume detection on startup
- **Agent loop**: `bin/wt-loop` — SIGTERM handling for clean exit with WIP commit
- **State schema**: new fields in `orchestration-state.json` (`shutdown_at`, per-change `last_commit`)
- **Engine**: `lib/wt_orch/engine.py` — resume validation (verify worktrees exist, branches match)
- **E2E scripts**: `tests/e2e/run.sh`, `run-complex.sh` — `--project-dir` flag
- **Config**: no orchestration.yaml changes needed
- **Worktrees**: preserved across shutdown — not removed during graceful stop
- **wt-web**: Settings page gains shutdown/resume controls, API gains `/api/{project}/shutdown` endpoint
