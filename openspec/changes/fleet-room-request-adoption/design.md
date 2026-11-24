## Context

`engagement-takeover` watches open engagements. `set-fleet-ask` is the only opener, so a request
posted into a relation room with `sac send` is invisible to it (B-233). Measurements in
`proposal.md`: of 66 untracked project-addressed requests in three days, 36 were answered without
a link and 8 not at all.

## Goals / Non-Goals

**Goals:**
- A request posted straight into a relation room that nobody answers is noticed and moved on,
  like one sent through `set-fleet-ask`.
- A request answered without a link is not treated as open.
- No surprise on deploy: requests that existed before adoption was switched on are not adopted.

**Non-Goals:**
- No change in `set-agent-comm`; nothing is posted on the bus by the framework.
- No adoption from a project's own room or a room of two sessions; no adoption of a request
  addressed to one session.
- No stored request text — an adopted engagement is the same pointer as an asked one.

## Decisions

### D1 — Relation rooms only, project-addressed only
A relation room is `dm-<a>--<b>`; a REQUEST/QUESTION heading in a file whose seat belongs to `a`
is addressed to `b` (and vice versa). Unaddressed and `→ b` are adopted; `→ b#<id>` is a session
conversation (that session's own wait handling covers it), and any other addressee is skipped.
*Alternative rejected:* adopting session-addressed requests — the watch would interrupt and could
replace an ordinary, operator-driven session, which the takeover never touches.

### D2 — Closure: linked reply, or the addressed project's first unlinked ANSWER after it
Measured: 36 of 66 were answered with an unlinked ANSWER. An ANSWER linked to a different request
does not close it; a FACT or another REQUEST does not either. Asked engagements keep linked-only
closure — their desk is told to link, and changing it would weaken a contract already in use.

### D3 — Forward only, with a watermark beside the store
`fleet-engagement-adopt.json` holds the epoch at which adoption was first switched on; entries
older than it are never adopted. A second bound — 24 h — stops a request whose closed record was
pruned (30-day retention) from being adopted again. Entries younger than 90 s are left for one
round, so a `set-fleet-ask` that has posted but not yet recorded the timestamp is not doubled.
A room file last written before the later of the watermark and 24 h ago is not opened.

### D4 — Unclaimed first, then the existing ladder
An adopted engagement has no desk. Each round: the project's live framework desk (an inventory
row holding an open `desk` mandate for the project) is assigned without counting a handover. With
no live desk, nothing happens until the request is one stall bound old — giving the project's
ordinary sessions time to answer — then a desk is started with a takeover whose `from_seat` is
empty, and assigned (again no handover). After assignment the request is an ordinary open
engagement.

**Not when a live session has read it** (added after M3/M4). Measured over seven days: 81 of
108 answered room requests were answered after more than five minutes (median 104 min). A desk
started at five minutes would, for most of them, work in parallel with a session already on it.
The bus keeps a per-room, per-reader cursor of the last entry read from each writer
(`cursors.json`); a live seat of the addressed project whose cursor is at or past the request
holds it, and no desk is started. An unreadable cursor store counts as unread — that direction
keeps a request from stopping, which is the change's purpose. *Alternative rejected:* a longer
grace — 64 of 108 were still answered after 30 minutes, so no single bound separates "someone
is on it" from "nobody saw it"; the cursor does.

The desk is recorded on the engagement even when its answer closed the record first (M3).

### D5 — The unclaimed desk is told so
The takeover block says nobody picked the request up and the fleet started this desk for it; its
first FACT says the request is now held by it. No predecessor transcript is named.

## Risks / Trade-offs

- [An unlinked ANSWER to something else closes an adopted request] → accepted: it errs toward
  quiet, and a request answered by an unrelated ANSWER in the same pair room within minutes is the
  rare case; the measured alternative (linked-only) mis-opens 36 of 66.
- [A project that cannot host a desk (not enrolled, not trusted)] → the start fails each round and
  is logged; the engagement stays open and waiting on the map, which is the honest state.
- [Scanning 70 rooms each minute] → only files touched since the watermark are opened, and only
  heading lines are matched.
