## Why

The fleet's project menu can say an agent is *working*, and it can say the log
holds no open tool call — but it cannot say **whether writing to that session
now would be pointless**. A session whose turn ended, a session whose turn ended
while a background command still runs, and a session actively producing tokens
all render the same way today, so the one thing a reader wants from that column —
*who is waiting for me, and for how long* — has to be worked out by opening tiles.

Two measurements taken on 2026-08-28 change what is possible here:

- The runtime record (`~/.claude/sessions/<pid>.json`) carries a **four-value
  status** — `busy`, `shell`, `idle`, `waiting` — and `shell` is exactly
  *"the prompt is free but a background command is still running"*. Measured in
  the binary of runtime 2.1.251: `status = (base === "idle" && hasRunningBackgroundBash) ? "shell" : base`.
- That status is **not the stale field this repo recorded on 2026-08-18**.
  `statusUpdatedAt` matched the last log entry's own timestamp in **10 of 10**
  live sessions that had a log, while the log's **mtime** was up to **90 minutes**
  off in 2 of those 10 — the file gets rewritten without new entries. A live
  pty probe measured the transitions at `idle → busy` in **0.6 s**, `busy →
  shell` when the agent backgrounded a command, and `shell → busy → idle` on
  completion, each stamp landing within **0.2 s** of the change.

So "how long has this session been waiting for a person, with nothing running"
is now a measurable quantity rather than an inference, and the project menu is
where it is worth spending.

## What Changes

- **New: a measured input-wait state per agent.** The runtime record's `status`
  and `statusUpdatedAt` are read alongside the log-derived state. `idle` with
  nothing outstanding becomes *waiting for input*, with the **duration** it has
  been waiting; `shell` becomes *not waiting — a background command is running*;
  `busy` stays working; `waiting` (a permission prompt or worker request) is
  carried with its reason.
- **New: an escalation on that duration** — a session waiting for input is
  unmarked under **15 s**, marked **amber** from 15 s, and **red** from
  **3 minutes**. The thresholds are declared in one place, on both sides.
- **The project menu carries the escalation**, on the project row and on the
  group header, so a collapsed group cannot hide a session that has been waiting
  four minutes.
- **`unknown` stops being amber.** Amber now means "waiting for you"; a state
  that could not be measured gets its own shape (a dashed marker) rather than a
  colour it would share with a different meaning.
- **A missing `status` key is never read as idle.** Headless runs (`entrypoint:
  sdk-cli`) carry no status at all — measured again on 2026-08-28, still true —
  and reading absence as `idle` would report a working orchestration agent as
  waiting for a person.

## Capabilities

### New Capabilities
- `agent-input-attention`: what a session is waiting for, measured from the
  runtime record — working, background-busy, waiting for input (with duration),
  or stopped at a prompt — and the escalation the surface renders from it.

### Modified Capabilities
<!-- None. `agent-fleet-state` lives in the unarchived `fleet-view` change and
     its requirements are unchanged: the log still decides working-vs-not, and
     this capability composes onto it rather than replacing it. -->

## Impact

- `lib/set_orch/fleet/state.py` — reads the record's status vocabulary; new
  fields on `AgentState`. The existing `state` values keep their meanings.
- `lib/set_orch/api/fleet.py` — the agent payload carries the new fields.
- `web/src/lib/fleetAttention.ts` — thresholds, tone resolution, tally.
- `web/src/components/FleetProjectColumn.tsx`, `web/src/pages/Fleet.tsx` — the
  escalation on the project row, the group header and the tile's state line.
- Tests: `tests/unit/` for the state and API layers, `web/src/**/*.test.ts(x)`
  for the tone and tally.
