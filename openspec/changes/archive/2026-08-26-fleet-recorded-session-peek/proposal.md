## Why

The restore disclosure now lists everything recorded for a project that was not open, and two
things about that list make it unusable at the size it actually reaches.

**One label names several conversations.** An entry is keyed on the session id and a `--resume`
mints a new one, so one named agent accumulates one entry per resume. Measured on the live
record 2026-08-26: six rows read `…-bugfix2` (last seen 15.1h / 36.6h / 2.0d / 2.0d / 2.8d /
3.9d ago) and a second label repeats five times. The list is honest and nobody can choose from
it — registered as **B-80**.

**And the only thing distinguishing them is an age.** The question a person actually has in
front of that list is *which conversation was this*, and the answer is on disk: the transcript
the entry would be resumed from. Reading its last few turns costs a tail read and answers the
question without resuming anything — no agent started, no context loaded, nothing charged.

## What Changes

- Repeated labels in the recorded list render as **one lineage row** — the label, how many
  conversations it holds, the newest one's age — which opens to the individual entries. A label
  holding one entry is unchanged.
- A recorded entry can be **peeked at**: its last few turns are read from the transcript on
  request and shown inline, without resuming the session or starting anything.
- The peek is a READ of a project's data at runtime: it is rendered and never written down —
  not to a cache, not to a log, not to `localStorage`, not to any committed artifact.
- An entry with no readable transcript says so where the peek would be, rather than showing an
  empty panel that reads like a session with nothing in it.

## Capabilities

### New Capabilities

- `fleet-recorded-session-peek`: reading the last turns of a RECORDED session — one that no
  process is on — so a person can tell which conversation an entry is, without resuming it.

### Modified Capabilities

- `agent-fleet-restore`: the surface requirement gains how a repeated label is presented and
  that an entry can be peeked at before it is picked.

## Impact

- `lib/set_orch/api/fleet.py` — one new route over the roster entry's own `session_log`; the
  parse itself is `fleet/conversation.py`, unchanged and already used by the live-agent log.
- `web/src/lib/fleetRoster.ts` — grouping the recorded entries by label into lineages.
- `web/src/components/FleetRestore.tsx` — the lineage row, and the peek panel.
- No new persistence, no schema change, no migration. The roster document is untouched.
