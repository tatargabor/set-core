## Why

Work across the fleet stops on the owner's answers, and there is no single place that shows what
is waiting on them. Stated by the user on 2026-10-19 (dictated): *"mi maradt el, vagy mi az, amit
el kell dönteni, az hol jön fel, hol látom. Vagy a fleet-en hol tudom megnézni"* — and a simple
view on the fleet screen, because a chat channel is not the best place to work such a list from.

Measured the same day: the fleet's own "awaiting a human" count read **3** across all projects,
with **53 of 58 projects unmeasured**, while a consumer's own coordinator reported **more than
twenty tickets** held on the owner's answers, and its room carried **dozens of items addressed to
the owner** — as prose (`→ <owner>`) inside broadcasts, which nothing can count. The fleet sees only the
framework's own run state; the two places the owner's open questions actually live are invisible
to it.

## What Changes

- One list of everything waiting on the owner, from four sources, **each counted and shown
  separately, and each able to say it could not be read**:
  1. **agent questions** — agents in a waiting-for-input attention class, plus questions the
     question relay is holding (already measured);
  2. **framework run state** — the existing `awaiting` kinds: manual, stalled, orphaned, decision
     (already measured);
  3. **project questions** — open questions and decisions a project publishes through a declared
     status-contract read command (**new; shape to be agreed with a consumer on the bus before it
     is built**);
  4. **bus entries addressed to the owner** — read through a machine-readable view the bus
     provides (**new; addressee and command to be agreed with the bus's maintainers before it is
     built**).
- A **"waiting on you" control** in the fleet header carrying the total and an unmeasured marker,
  opening a floating panel (it pushes nothing) that lists the items oldest first, grouped by
  project, with what each item blocks (a release, a change) and a link to where it can be
  answered: the agent's tile, the project's status row, or the bus message.
- `GET /api/fleet/waiting-on-you` — the same list as one answer, so another surface (a chat
  notifier, a copilot) reads the list rather than assembling a second one.

## Capabilities

### New Capabilities
- `fleet-waiting-on-you`: the owner's queue — its four sources and their separate measurement,
  the API answer, the header control and its panel, and the persistence boundary on item content.

### Modified Capabilities
- None. The project-side command is a declared read command under the existing
  `project-status-contract` rules (set-core keeps no built-in list of contract commands), so the
  contract's requirements do not change; the fleet merely consumes one more declared command.

## Impact

- `lib/set_orch/fleet/waiting.py` (new, Layer 1, domain-free) — aggregation of the four sources;
  `lib/set_orch/api/fleet.py` — the route.
- Reuses `fleet/awaiting.py`, `fleet/question_relay.py`, the agent attention classes in
  `fleet/state.py`, and the project-status contract reader.
- `web/src/components/FleetWaitingOnYou.tsx` (new), the fleet header.
- External agreements: a consumer (the declared command's shape) and `set-agent-comm` (an owner
  addressee and a machine-readable view). Sources 3 and 4 are built only after those agreements are
  on the record; sources 1–2, the API, and the panel do not depend on them.
- Persistence: item titles are project and conversation content — displayed at request time,
  never logged, cached to disk, or written into any artifact.
