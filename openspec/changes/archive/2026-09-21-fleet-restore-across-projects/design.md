## Context

The per-project restore (`RestoreForProject`) reads `GET /api/fleet/roster/{project}` and posts
`POST /api/fleet/roster/{project}/restore` with an explicit `keys` list. The fleet-wide listing
`GET /api/fleet/roster` returns `{project, entries, last_seen, running}` per project. None of
these routes needs to change.

## Decisions

### D1 — Fan out on the client, not a new batch route

The restore route already takes a selection, and its result is per project
(`RestoreResult.project`). A batch route would need a second definition of "complete" and a
second known-roots guard path. Both are drift risks this surface has already paid for
(`summarise()` takes `complete` from the server for this reason). Posting one project at a
time keeps the server as the only judge of each project's outcome, and the client only sums.

The posts run **sequentially**, not in parallel: each one starts agents through the owner
service, and starting N agents at once across projects is a load the per-project path never
produces.

### D2 — Read each project's list only when that project is opened

At 34 projects, each `GET /api/fleet/roster/{project}` also asks liveness. Reading all of
them when the dialog opens would cost 34 reads to show a list of names. The fleet-wide
listing already carries the count and age for each project row, so a project's entries are
fetched when its row is expanded, and each project is fetched once per opening of the
dialog. Nothing is cached beyond that: the peek module's persistence rule (display at
runtime, persist nothing) applies to the roster data too.

### D3 — The offer counts from the entries, never from the listing

The listing's `entries - running` looks like "restorable", but it is not: it includes
unresumable entries. The selection is made from fetched entries only, and `offerAcross()`
reuses `offerFor()` for each project, so the number on the button and the keys posted come
from one derivation.

### D4 — Aggregate result: complete only if every part was complete

`summariseAcross()` takes one `RestoreSummary` or one error for each project attempted.
`complete` is true only when every project posted successfully **and** its server result was
`complete`. A project whose request failed is listed with its error. It is never folded into a
count of zero started, because nothing was attempted there.

### D5 — Placement and weight

The control is a `Chip` (the `History` mark and the count of recorded entries not running)
at the end of the attention row. The count is labelled as recorded sessions, not as
restorable ones, because the listing cannot know how many are resumable (D3). When the
listing is unreadable or empty, no chip is drawn. That matches the per-project rule that a
control which would do nothing is not offered.

## Risks

- **A mis-aimed click starting many agents.** This is the defect behind the per-project arming
  rule (21 agents, 2026-08-23), and it is larger here because the blast radius spans projects.
  Mitigation: nothing is selected by default, there is no "all" act, and the confirmation
  names both the agent count and the project count.
