## Why

An agent that cannot go on without the owner usually does not open a question tool. It ends its
turn with a line that starts `NEED INPUT:` — the hand-over marker the consumer family's hooks
already define (`keep-going.mjs`: *"Stop only when (a) you need a concrete decision from the human
… — put it on its own line starting with `NEED INPUT:` — or (b) everything is finished — start a
line with `ALL DONE:`"*), and which `set-agent-comm`'s stop hook honours since 2026-11-21 (it never
sends such a turn back).

The fleet reads that turn as an ordinary finished one: `quiet`, attention `input`, the tab's green
"ready to read" circle, no question mark. Reported 2026-11-23 by the user with a screenshot of a
session whose last message ended `NEED INPUT: Írd ide ebbe a sessionbe, hogy „mehet a push”` and
whose turn was done: *"ez is kellene hogy a fleet detektalja hogy input needed"*. So a request
addressed to the reader renders exactly like a report the reader may read whenever — the calm
direction, and the one B-168 already closed for `AskUserQuestion`.

## What Changes

- The fleet reads the **last assistant text of a finished turn** for the hand-over marker, with
  the family's own pattern: a line starting (after optional markdown emphasis or a quote mark)
  with `NEED INPUT:` or `ALL DONE:`.
- A new agent field **`handover`**: `need_input`, `all_done`, or `null`. It is set only when the
  log shows no outstanding call AND the last text in the tail was said by the agent — a reply
  from the person after the marker clears it.
- **`need_input` raises the attention class to `prompt`**, the class an open question already
  has. So the tab's warning, the project row's question tint and marker, and the state line treat
  it the way they treat an `AskUserQuestion` — the agent is stopped in front of a person and the
  answer is a sentence only the reader can write. The wait duration stays the record's
  `statusUpdatedAt` age (the turn ended at that moment).
- `all_done` is carried but changes no class: a finished turn is already `input` / green.
- The state line on the tile says `needs your input` for such an agent.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `agent-input-attention`: one requirement added — a declared hand-over marker in a finished
  turn's last text is read, and `NEED INPUT:` makes the session a `prompt`.

## Impact

- `lib/set_orch/fleet/state.py` (Layer 1, domain-free: the marker is a framework-neutral
  convention, not project content) — marker detection and the attention raise.
- `lib/set_orch/api/fleet.py` — the `handover` field on both agent payloads.
- `web/src/lib/fleetAttention.ts` (the tally's question count), `web/src/pages/Fleet.tsx` (state
  line).
- Persistence: the marker's text is never logged or stored; only the class name crosses the API.
