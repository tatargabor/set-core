## Why

The fleet screen is organised by project, so reaching the agent you were just working with means
finding its project on the left first. While working, the reader moves between roughly ten agents
spread over several projects, and every switch costs a project click before the agent click.
Stated by the user on 2026-10-19 (dictated): *"ne kelljen a projektenken kattintgatnom, hogy az
adott agentet megtaláljam"* — a mode that puts the agents most recently written into on one screen,
as if they were one project.

The signal the ordering needs already exists — `last_human_input_seconds`, measured from each
session's transcript — but measured on the live fleet the same day it was **absent for 6 of 19
agents**, one of them working at that moment. The value is read from a bounded 256 KB tail, and an
agent given a long task fills that tail with tool traffic. So the agent the reader most recently
handed work to is the one most likely to fall off a recency list. The mode is not buildable on the
signal as it stands; that gap is part of this change.

## What Changes

- A **latest mode** toggle beside the PM mode toggle in the fleet header, with a number beside it
  (how many agents; default 10). Turning it on touches no agent; turning it off restores the
  arrangement underneath.
- While on, the agent area shows the N agents a person most recently wrote into, **across all
  projects**, through the existing grid, enlarged view, tab strip and column choices. Its view
  memory (columns, enlarged tile, open terminals) is kept under its own key, apart from every
  project's.
- **Live order** (reversed 2026-10-23, see design D3): the set is re-ranked most recent first on
  every poll, held while the pointer is over the tabs or tiles. Was: stable placement — an agent that
  becomes recent takes the slot of the least-recent one and no other tile moves. A re-sort control
  re-orders on request.
- No project is selected in the project column while the mode is on, and every tile names its
  project.
- Latest mode and PM mode are mutually exclusive: turning one on turns the other off.
- An agent with no terminal opens its log, as PM mode already does.
- Per-project controls (agent drag-reorder, docks, the project's files/board panels) are not
  offered in the mode.
- **Server:** the last human input is found beyond the bounded tail when the tail holds none,
  and remembered in memory per transcript, so `null` means *this transcript holds no message from
  a person*, not *not seen in the last 256 KB*.

## Capabilities

### New Capabilities
- `fleet-latest-mode`: the cross-project recency view of the fleet — its toggle, its count, which
  agents it selects and in what order, how placement stays stable, and how it coexists with PM mode
  and the project column; plus the human-input measurement reaching beyond the bounded tail, which
  the selection depends on.

### Modified Capabilities
- None in `openspec/specs/`. The human-input requirement this change deepens lives in the
  unarchived `fleet-input-attention` change (`When a person last wrote here is measured, and it is
  not the wait`); its *absent means not seen in the bounded tail* clause is narrowed here by an
  ADDED requirement rather than a MODIFIED one against a spec that has not reached `specs/` yet.

## Impact

- `lib/set_orch/fleet/state.py` (Layer 1, domain-free) — the human-input search beyond the tail
  and its in-memory cache. No new API field; `last_human_input_seconds` keeps its name and meaning
  except that `null` becomes rarer and more honest.
- `web/src/pages/Fleet.tsx`, `web/src/lib/fleetViewState.ts`, a new `web/src/lib/fleetLatest.ts`
  (pure selection + stable-placement logic), the header toggle, the project column's selection.
- Tiles today take their project root from the selected project; in this mode each tile must take
  its own agent's project root. That is the main implementation risk.
- No persistence beyond the browser's existing view-state storage; nothing derived from a
  transcript is written to disk.
