## Context

The orchestrator currently dispatches all pending changes in a flat model — any change whose dependencies are satisfied gets dispatched up to `max_parallel`. For complex projects (15+ changes), this means 4+ hours of uninterrupted execution with no intermediate human verification. Problems like missing design application, wrong direction, or skipped functionality are only discovered after the entire run completes.

The existing infrastructure provides building blocks:
- `checkpoint` merge policy with `trigger_checkpoint()` — but quantity-based, not phase-based
- `post_phase_audit` — LLM-based spec-vs-implementation gap detection, but runs only at end
- `change_type` field (infrastructure/schema/foundational/feature/cleanup) — natural phase ordering
- `depends_on` array — already gates dispatch on dependency completion
- `send_email()` / `send_summary_email()` — Resend integration for notifications
- `generate_report()` — HTML dashboard with auto-refresh
- `auto_replan_cycle()` — already tracks completed work across cycles
- `smoke_dev_server_command` directive + `_ORCH_DEV_SERVER_PID` — existing pattern for auto-starting dev servers with health checks (added in gate-reliability commit)
- Monitor self-watchdog (`MONITOR_IDLE_TIMEOUT`) — detects stalls and auto-recovers
- Merge timeout protection (`MERGE_TIMEOUT`) — prevents infinite merge pipeline hangs

## Goals / Non-Goals

**Goals:**
- Planner assigns a `phase` number (1..N) to each change during decomposition
- Dispatcher only dispatches changes from the current phase
- On phase completion: git tag, create worktree, auto-detect and start dev server, send email
- Orchestrator continues to next phase immediately (non-blocking)
- Human reviews running milestone environment in parallel; stops orchestrator if needed
- Dashboard and HTML report show phase progress
- Dev server command auto-detected from project (package.json, docker-compose, etc.)

**Non-Goals:**
- Blocking approve/reject gate (human uses stop/resume instead)
- Automatic screenshot comparison with design
- Automatic correction on rejection (human intervenes manually)
- Phase-specific token budgets
- Changing the replan cycle mechanism (phases are within a single plan cycle; replan is orthogonal)

## Decisions

### D1: Phase = milestone, single concept

Phase number in plan JSON is the milestone. No separate milestone entity.

```json
{
  "changes": [
    { "name": "db-schema", "phase": 1, ... },
    { "name": "auth",      "phase": 1, ... },
    { "name": "catalog",   "phase": 2, ... }
  ]
}
```

**Why**: Simplest model. The planner already understands change_type ordering — adding a phase number is a natural extension. A separate milestone entity would require additional bookkeeping with no clear benefit.

### D2: Planner assigns phases, user can override

The decompose prompt instructs the planner to assign phases:
- Phase 1: infrastructure, schema, foundational
- Phase 2+: features (grouped by domain coherence)
- Last phase: cleanup-after, polish

User can override in `orchestration.yaml`:
```yaml
milestones:
  enabled: true
  # Override phase assignments (optional):
  phase_overrides:
    db-schema: 1
    catalog: 3
```

**Alternative considered**: Auto-assign from `change_type` without planner involvement. Rejected because the planner has spec context to make domain-coherent groupings (e.g., "auth + user-profile should be same phase even though both are 'feature'").

### D3: Non-blocking checkpoint with worktree + dev server

On phase completion:
1. `git tag milestone/phase-N` on current HEAD
2. Create read-only worktree from tag at `.claude/milestones/phase-N/`
3. Auto-detect and start dev server in worktree on port `base_port + N`
4. Send email with phase summary + link
5. Continue to next phase immediately

**Why non-blocking**: The user explicitly wanted parallel review — check previous phases while new ones run. A blocking gate adds ceremony without value since the user's action on problems is always "stop orchestrator, fix, resume."

### D4: Dev server auto-detection

Reuses the pattern from `smoke_dev_server_command` (gate-reliability commit) — the orchestrator already knows how to start a dev server with health checks and PID tracking. Milestone servers extend this pattern to per-worktree instances.

Detection order (first match wins):
1. `orchestration.yaml` → `milestones.dev_server` (explicit override)
2. `smoke_dev_server_command` directive (if already configured for smoke tests, reuse it)
3. `package.json` → `scripts.dev` → `npm run dev` (or `bun run dev` if bun.lockb exists)
4. `docker-compose.yml` or `compose.yml` → `docker compose up`
5. `Makefile` with `dev` or `serve` target → `make dev` / `make serve`
6. `manage.py` → `python manage.py runserver`
7. No server detected → skip server start, still tag + email

Port assignment: `PORT=<base_port+N>` environment variable. Base port from `milestones.base_port` (default: 3100, same range as E2E).

**Alternative considered**: Reuse `_ORCH_DEV_SERVER_PID` global directly. Rejected because milestones need multiple concurrent servers (one per phase), while smoke uses a single global server. Milestone servers store PIDs in state per-phase instead.

### D5: Phase state tracking in orchestration-state.json

```json
{
  "current_phase": 2,
  "phases": {
    "1": { "status": "completed", "tag": "milestone/phase-1", "server_port": 3101, "server_pid": 12345, "completed_at": "2026-03-14T..." },
    "2": { "status": "running", "tag": null, "server_port": null },
    "3": { "status": "pending", "tag": null, "server_port": null }
  }
}
```

Phase statuses: `pending` → `running` → `completed`

### D6: Phase-gated dispatch

`dispatch_ready_changes()` adds one filter: only dispatch changes where `change.phase <= current_phase`. When all changes in `current_phase` are terminal (merged/failed/skipped), advance `current_phase` and trigger milestone checkpoint.

Dependencies still apply within and across phases (a phase-2 change can depend on a phase-1 change — the dependency must be satisfied regardless).

### D7: Cleanup on orchestration complete

When orchestration finishes (all phases done, or stopped):
- Kill all milestone dev server processes (stored PIDs in state)
- Remove milestone worktrees
- Keep git tags (lightweight, useful for history)

### D8: Email content for milestone

Subject: `[wt-tools] <project> — Phase N complete (M/T changes)`

Body:
- Phase summary: which changes merged, token cost
- Dev server URL: `http://localhost:<port>`
- Dashboard URL if wt-web is running
- Note: "Orchestrator continues automatically. Stop with: wt-orchestrate stop"

## Risks / Trade-offs

**[Risk] Port conflicts** → Milestone servers use ports 3101, 3102, etc. Could conflict with other services. Mitigation: configurable base_port, check port availability before starting.

**[Risk] Worktree accumulation** → Each completed phase creates a worktree. For 5 phases, that's 5 worktrees with full project copies. Mitigation: cleanup on orchestration complete; configurable max_milestone_worktrees (default: 3, oldest removed when exceeded).

**[Risk] Dev server process leaks** → Server processes could outlive orchestrator crash. Mitigation: store PIDs in state; cleanup function checks on startup; worktree removal kills associated processes.

**[Risk] Planner phase quality** → Planner might make poor phase assignments (too many phases, unbalanced sizes). Mitigation: prompt instructs "2-5 phases, roughly equal size"; user can override via yaml.

**[Risk] Cross-phase merge conflicts** → Later phases modify files touched by earlier phases. Mitigation: existing merge conflict resolution applies; milestone worktrees are read-only snapshots so they don't interfere.
