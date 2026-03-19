# Spec: Orchestrator Resume Mode

## Requirements

### REQ-ORM-01: Auto-resume detection
When `wt-orchestrate start` is called and a state file exists with active changes (running, pending, verifying, stalled, dispatched), skip digest/planning and go directly to the monitor loop.

### REQ-ORM-02: Zombie process detection on resume
On resume, check all `running` changes for dead PIDs. Don't mark them failed — let the monitor's existing stall detection handle recovery.

### REQ-ORM-03: Sentinel state backup
When sentinel detects `done`/`stopped` and decides to clean state, backup the state file to `.bak` instead of deleting it. Never delete `orchestration-state.json` without backup.

### REQ-ORM-04: Resume subcommand alias
Add `wt-orchestrate resume` as an alias for `start` with auto-resume forced (skip planning even if plan file is stale).

### REQ-ORM-05: Directives file preservation
On resume, read directives from `wt/orchestration/directives.json` (written by previous start). Error if missing.

## Scenarios

### WHEN start is called with existing state and active changes
THEN no digest runs, no decompose runs
AND monitor loop starts within 5 seconds
AND existing worktrees are preserved

### WHEN start is called with state file but all changes are done/failed
THEN normal planning flow runs (no active work to resume)

### WHEN sentinel sees done/stopped
THEN state file is backed up to .bak, not deleted
AND next start can auto-resume from backup if needed

### WHEN resume is called with no state file
THEN error with message explaining state file is required
