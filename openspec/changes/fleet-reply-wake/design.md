## Context

`fleet/engagement.py` records each request sent through the fleet (`set-fleet-ask`): the
asker's seat, the room, the request's timestamp. `refresh()` marks it `answered` when the bus
links a reply to it. The takeover round (`api/fleet_mandate.takeover_round`, every minute)
already refreshes and acts on open engagements, and the inventory rows carry each live
agent's seat, runtime status, last movement, last human input and fleet terminal label.

## Decisions

**D1 — A separate pass over answered engagements, not a hook on the refresh.** `refresh()` is
called from three places, and a reply marked answered by the listing's refresh would never be
seen by a hook on the round's own refresh. The round therefore also walks `answered`
engagements that carry no wake outcome yet, and records one. That record is the "at most
once".

**D2 — "Has not moved since the reply" is measured, not assumed.** If the asker moved after the
reply's timestamp, something already brought the reply to it (the bus's stop hook reports mail
at a turn end) or it was given other work. Waking it then is the needless wake the owner ruled
out. The row's `last_movement_seconds` against the reply's age decides it, with 30 s slack for
the stop hook's own write.

**D3 — Type the line without Esc.** The takeover interrupt sends Esc first, because it stops a
running turn. Here the turn has ended. An Esc at a free prompt would clear anything half-typed
there, so the line and Enter are written alone.

**D4 — Matching the asker.** The engagement holds a seat (`<project>#<session prefix>`). The
row is the one whose `seat` equals it, or else whose session id starts with the seat's suffix.
A seat that outlived its session (`/clear`) matches nothing and records `gone`. That limit is
stated, not hidden: part 1 of B-215, the bus's own wake, is set-agent-comm's.

## Risks / Trade-offs

- [An answered engagement from before this ships wakes somebody] → replies older than 2 h are
  recorded `too-old` and never wake.
- [The owner is about to type] → the two-minute operator-present guard. The opt-out from
  `fleet-auto-answer-session-off` holds here too.
