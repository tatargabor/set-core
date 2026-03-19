## Why

E2E craftbrew Run #5 exposed 5 framework bugs that block autonomous orchestration. Each bug independently causes dispatch failure, infinite loops, or silent data corruption. Together they make E2E runs require constant manual intervention.

## What

Fix 5 issues discovered during Run #5:

1. **Scaffold branch naming** — `run-complex.sh` creates `spec-only` branch but orchestrator expects `main`/`master` for merge target. Fix: rename branch in scaffold script.

2. **build_broken_on_main flag never clears** — After post-merge build fails (e.g., due to conflict markers), the flag blocks all future dispatches permanently. Fix: auto-retry build periodically and clear flag on success.

3. **Memory cross-project injection** — Memory hooks inject memories from the set-core project into craftbrew agent sessions, causing "4/4 done" artifact loops. Fix: hooks must resolve project name from worktree CWD, not caller session.

4. **orchestration.yaml default model** — Config template uses `opus` but should offer `opus-1m` for 1M context. Fix: update config template.

5. **Python monitor event gap** — Python monitor doesn't emit events to bash sentinel log, causing false "no progress for 301s" watchdog alarms. Fix: emit heartbeat events from Python monitor.

## Scope

- `tests/e2e/run-complex.sh` — branch rename
- `lib/set_orch/loop.py` or `merger.py` — build_broken_on_main auto-clear
- `bin/set-hook-memory-*` — project name resolution
- `wt/orchestration/config.yaml` template — default model
- `lib/set_orch/engine.py` — heartbeat events
