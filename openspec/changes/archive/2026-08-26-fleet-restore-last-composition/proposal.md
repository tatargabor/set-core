## Why

The restore offer is built from the roster's whole 30-day retention window, so it promises
back every conversation ever recorded under a project rather than the composition the user
actually had open. Measured on this machine's own `fleet-roster.json` on 2026-08-26:

```
18 projects   233 recorded entries   13 seen in the last discovery round
worst single project: 109 recorded,  4 open
the reported one:      24 recorded,  3 open
```

The duplication is structural, not noise: an entry is keyed on the session id, and a
`--resume` produces a new session id, so one named agent accumulates one entry per resume —
in the reported project a single label held **five** recorded session ids, of which one was
the live conversation. The control's own number is honest about what the code will do
(`Restore 9 of 24`), and what the code will do is start nine sessions nobody left open, on a
screen where a mis-aimed click has already cost 21 started agents. Reported by the user
2026-08-26 with a screenshot; registered as **B-78**.

## What Changes

- The roster document records **when the last discovery round happened**, stamped by the
  write that already stamps every entry it saw. "Seen in the last round" then becomes an
  exact equality against that stamp, not a time-window heuristic.
- Reading a project's record reports, per entry, whether it was **in the last round** — that
  is, whether it was open when the fleet was last observed — alongside the resumability and
  liveness it already reports.
- Restore accepts an optional **explicit set of entry keys**. The existing bodiless call
  keeps its meaning — the whole recorded list — so nothing that calls it today changes.
- The fleet surface's primary restore offer becomes **the last composition**, stating the
  age of that observation. Everything recorded but not in that composition stays reachable
  behind an expander with per-entry selection; nothing is silently dropped.
- A last round that contains no entries reads as *"nothing was open when the fleet was last
  seen"* — never as the previous round's composition.

## Capabilities

### New Capabilities

<!-- None. Both halves of this are changes to behaviour that already ships. -->

### Modified Capabilities

- `agent-fleet-snapshot`: the record gains the round it was written in, and a read reports
  per entry whether it belongs to the last round.
- `agent-fleet-restore`: restore is no longer defined as "the whole recorded list only" — it
  takes an optional explicit selection, and the surface's default offer is the last observed
  composition rather than the whole record.

## Impact

- `lib/set_orch/fleet/roster.py` — document-level round stamp on write; `in_last_round` on read.
- `lib/set_orch/fleet/restore.py` — an optional `keys` filter over the entries it attempts.
- `lib/set_orch/api/fleet.py` — an optional request body on `POST /api/fleet/roster/{project}/restore`.
- `web/src/lib/fleetRoster.ts` — the offer splits into the composition and the remainder.
- `web/src/components/FleetRestore.tsx` — the primary act, the expander, the selection.
- Existing callers of the bodiless restore route are unaffected; no stored roster needs
  migrating (a document with no round stamp reports no last round rather than a false one).
