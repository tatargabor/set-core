# Design: orchestration-pause-resume

## Context

Process hierarchy during orchestration:

```
set-sentinel (supervisor)
  └── set-orchestrate (bash orchestrator)
        └── set-orch-core engine monitor (Python monitor loop)
              ├── set-loop (Ralph loop 1) → claude session + child processes
              ├── set-loop (Ralph loop 2) → claude session + child processes
              └── dev-server (optional)
```

Current state:
- `set-sentinel --shutdown` sends SIGUSR1, which triggers SIGTERM to orchestrator
- Sentinel already writes `"shutdown"` to state after orchestrator exits (set-sentinel line 987)
- engine.py `cleanup_orchestrator()` always writes `"stopped"` (line 194) — sentinel overwrites after
- Ralph has SIGTERM trap (`cleanup_on_exit` in engine.sh line 128) that commits WIP but does NOT stop the loop or kill child processes
- Frontend has Shutdown button (works) and Resume button (only for "shutdown", not "stopped"; calls non-existent `/start` endpoint)

## Goals
- Ralph respects shutdown: finish current iteration, don't start next
- Web-initiated resume via new `/start` endpoint
- Shutdown progress visible in UI
- Per-change pause/resume with Ralph re-dispatch

## Non-Goals
- Changing sentinel's "shutdown" status write (already correct)
- Adding flag files or new status writers to engine.py (sentinel owns "shutdown")
- New CLI commands (existing ones work fine)

## Decisions

### D1: Ralph iteration stop via shutdown flag
**Choice**: On SIGTERM, set a `SHUTDOWN_REQUESTED` flag variable. The main loop checks this flag before starting a new iteration. Current iteration completes normally.

**Why**: This is the cleanest approach — no mid-iteration interruption, no WIP loss. The existing `cleanup_on_exit` trap already commits WIP on exit. We just need to prevent the `while` loop from continuing.

**Implementation in `lib/loop/engine.sh`**:
```bash
SHUTDOWN_REQUESTED=0
trap 'SHUTDOWN_REQUESTED=1; cleanup_on_exit' SIGTERM
# In the main loop:
while [[ $SHUTDOWN_REQUESTED -eq 0 ]]; do
    run_iteration
done
```

**Child process cleanup**: Extend `cleanup_on_exit` to find and kill child process group. Use `pkill -P $$` with 10s grace, then `pkill -9 -P $$`.

**Alternative considered**: Sending SIGSTOP to pause Ralph without killing — too complex, process stays in memory, machine shutdown would kill it anyway.

### D2: Sentinel owns "shutdown" status — no change needed
**Choice**: Keep current behavior. Engine.py writes "stopped" in its cleanup. Sentinel writes "shutdown" after orchestrator exits. The timing is safe: sentinel waits for child process exit before writing.

**Why**: The sentinel already does this correctly (set-sentinel lines 984-989). Adding a flag file or second writer creates race conditions. The only "race" is engine.py writing "stopped" first, then sentinel overwriting with "shutdown" — this is the intended order.

**No code change needed** in engine.py or state.py for the status distinction.

### D3: Start endpoint spawns detached sentinel
**Choice**: `POST /api/{project}/start` spawns `set-sentinel --spec <path>` via `subprocess.Popen` with `start_new_session=True`.

**Spec path resolution** (in order):
1. Read `orchestration-state.json` → `extras.spec_path` (if state exists from previous run)
2. Read `wt/orchestration/config.yaml` → look for `spec:` key
3. Fallback: scan for `docs/spec.md`, `docs/*.md`, `project-brief.md`

**Safety checks**:
- Read `sentinel.pid` → `kill -0` → if alive, return 409
- If state exists and is corrupt JSON → return 500 with detail
- Log the spawn to orchestration event log

**Alternative considered**: systemd user service per project — too heavy.

### D4: Shutdown progress via events
**Choice**: The orchestrator emits JSONL events during shutdown cascade. The web dashboard polls/streams these events to show a live progress list.

**Event sequence**:
```jsonl
{"type":"SHUTDOWN_STARTED","ts":"...","data":{"changes":["auth","cart","nav"]}}
{"type":"CHANGE_STOPPING","ts":"...","data":{"name":"auth","ralph_pid":12345}}
{"type":"CHANGE_STOPPED","ts":"...","data":{"name":"auth","exit_code":0,"duration_ms":2300}}
{"type":"CHANGE_STOPPING","ts":"...","data":{"name":"cart","ralph_pid":12346}}
{"type":"CHANGE_STOPPED","ts":"...","data":{"name":"cart","exit_code":0,"duration_ms":1800}}
{"type":"SHUTDOWN_COMPLETE","ts":"...","data":{"total_duration_ms":5100}}
```

**Frontend component**: `ShutdownProgress` — renders a simple list:
```
Shutting down...
  ✓ auth         stopped (2.3s)
  ◌ cart         stopping...
  ✓ nav          stopped (1.1s)
  ✓ dev-server   stopped
```

Shown on Dashboard when shutdown is in progress (between SHUTDOWN_STARTED and SHUTDOWN_COMPLETE).

### D5: Per-change pause stops Ralph, resume re-dispatches
**Choice**: Pause sends SIGTERM to Ralph (graceful iteration stop). Resume calls the dispatcher to spawn a new Ralph loop for the change.

**Why**: "Pause" that leaves Ralph running is confusing — the process consumes resources and may make API calls. Clean stop + re-dispatch is simpler and matches user expectations.

**Re-dispatch on resume**: The monitor loop in engine.py already has `dispatch_ready_changes()`. Resume sets status to "dispatched", and the monitor loop picks it up on next poll. If max_parallel is reached, return 429.

**Alternative considered**: Soft pause (Ralph alive but idle) — wastes tokens/resources, Ralph may time out during long pause.

## Risks / Trade-offs

- [Risk] `Popen` sentinel from API may not have correct PATH → Mitigation: resolve `set-sentinel` path relative to set-core installation, inherit environment from API process
- [Risk] Multiple rapid start calls could race → Mitigation: sentinel has flock guard, second instance exits immediately
- [Risk] Ralph may be in middle of long Claude session on SIGTERM → Mitigation: flag-based approach lets current iteration complete naturally; 90s timeout as safety net
- [Risk] Shutdown events may not reach web if orchestrator crashes mid-shutdown → Mitigation: frontend detects stale shutdown (no new events for 30s) and shows "Shutdown may have stalled"

## Open Questions

(none — all critical questions resolved during review)
