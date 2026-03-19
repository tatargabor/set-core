## Why

Complex projects (15+ changes) take 4+ hours to orchestrate and consume 6M+ tokens in a single run. Problems discovered late — design not applied, missing functionality, wrong direction — waste the entire budget. There's no intermediate checkpoint where a human can verify progress, catch issues early, and course-correct before the next batch runs.

## What Changes

- Planner assigns a `phase` number (1..N) to each change during decomposition, grouping them into milestones (foundation → core features → extended → polish)
- Dispatcher gates change dispatch by phase — only dispatches changes from the current phase
- State tracks `current_phase` and per-phase status
- On phase completion (all changes merged): git tag `milestone/phase-N`, create read-only worktree from tag, auto-detect and start dev server on unique port, send email notification, run post-phase audit
- Orchestrator continues to next phase without blocking — human reviews the running environment in parallel
- Dashboard shows phase progress with links to running milestone environments
- Human can stop orchestrator at any time if a phase doesn't look right, intervene manually, then resume
- Cleanup: milestone worktrees and servers are removed when orchestration completes

## Capabilities

### New Capabilities
- `milestone-phases`: Phase assignment in planner, phase-gated dispatch, phase state tracking
- `milestone-checkpoint`: Non-blocking checkpoint on phase completion — git tag, worktree, dev server, email notification, post-phase audit
- `milestone-server-detect`: Auto-detection of project dev server command from package.json/Makefile/docker-compose/etc.
- `milestone-dashboard`: Phase progress view in web dashboard with links to running milestone environments

### Modified Capabilities
- `orchestrator-tui`: Add milestone/phase progress display to the existing TUI dashboard
- `usage-display`: Include per-phase token usage breakdown

## Impact

- `lib/orchestration/dispatcher.sh` — phase-gated dispatch logic
- `lib/orchestration/monitor.sh` — phase completion detection + checkpoint trigger
- `lib/orchestration/planner.sh` — pass phase instruction to decompose prompt
- `lib/set_orch/templates.py` — decompose template: phase assignment instructions
- `lib/orchestration/auditor.sh` — tie audit to phase boundaries
- `lib/orchestration/state.sh` — phase state tracking helpers
- `bin/set-orchestrate` — resume/stop commands, phase-aware status
- `lib/web/` — dashboard milestone UI
- `lib/notifications/` — email templates for milestone notifications
- `orchestration.yaml` — new `milestones` config section
