## Why

An interactive agent nobody has typed into for days is not free. Watches, timers and bus messages
keep waking it, and each wake re-reads its whole context, so an abandoned session keeps spending
tokens. The owner closed nine such sessions by hand on 2026-11-07 and asked for it to happen on its
own: *„legyen ez automatikus, naponta zárja be őket majd visszahozzuk, legyen 2 napos azért inkább"*.

Nothing is lost by closing one: the fleet's roster already records every agent it has seen, and a
closed session stays resumable from it.

## What Changes

- A new command, `set-fleet-idle-close`, closes the fleet's interactive agents that have had **no
  human input for longer than a threshold** (default 48 hours), through the fleet's existing stop
  route.
- It keeps every agent whose idle time it cannot measure, and every agent that is in the middle of
  a tool call at that moment. Closing is the destructive direction, so doubt keeps the agent.
- `--dry-run` lists what it would close and closes nothing.
- Every close is appended to a local log with the label, project, session id and idle time, so the
  owner can see what went and bring it back from the roster.
- `set-fleet-idle-close install-timer` writes a daily systemd user timer for it. Nothing runs
  automatically until the timer is installed.
- The threshold is local config: `fleet_idle_close_hours`.

## Capabilities

### New Capabilities
- `fleet-idle-close`: closing the fleet's long-idle interactive agents on a schedule, and what it
  must never close.

### Modified Capabilities
<!-- none: restore already exists (agent-fleet-restore) and is used unchanged -->

## Impact

- New: `lib/set_orch/fleet/idle_close.py`, `bin/set-fleet-idle-close`, a unit test file.
- Reads `GET /api/fleet/agents` and calls `POST /api/fleet/agents/{label}/stop` on the running
  dashboard; no change to either route.
- A local log under the user's state directory. It holds session ids and project names, so it
  never goes into a repository.
