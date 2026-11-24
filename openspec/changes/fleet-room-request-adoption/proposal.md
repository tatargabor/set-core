## Why

The takeover watch (`engagement-takeover`) moves a stalled request on — but only a request that
has an engagement, and the only thing that opens one is `set-fleet-ask`. An agent that posts its
request straight into a relation room with `sac send` gets no record, so nothing notices when
nobody answers (B-233).

Measured 2026-11-24 over three days of relation rooms (`dm-<a>--<b>`): 110 cross-project
REQUEST/QUESTION entries, 24 tracked by an engagement. Of the 66 untracked ones addressed to a
project (not to one session), 21 got a linked reply, **36 got an unlinked ANSWER** from the
addressed project, 1 got some other entry, and **8 got nothing** — about three a day that wait
forever. The 36 matter as much as the 8: a record closed only by a linked reply would hold them
open and interrupt desks that had already answered.

## What Changes

- The takeover round **adopts** a cross-project request found in a relation room: a REQUEST or
  QUESTION by a seat of one project, unaddressed or addressed to the other project by name, newer
  than the moment adoption was first switched on, at least 90 s old, with no engagement for its
  room and timestamp. It becomes an `open` engagement with `source: room`.
- An adopted engagement is **answered** by a linked reply, or by the first unlinked ANSWER the
  addressed project posts in that room after it.
- An adopted engagement starts **unclaimed**. It is given the project's live desk when there is
  one; when there is none and the request is older than the stall bound, a desk is started for it
  with a takeover that says nobody picked it up. From then on the existing ladder applies.
- A request addressed to one session (`→ <project>#<id>`) is not adopted: it is a conversation
  between two sessions, not a request to a project.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `engagement-takeover`: a request posted straight into a relation room is adopted as an
  engagement, closed by a linked or unlinked answer, and given a desk when it is unclaimed.

## Impact

- `lib/set_orch/fleet/engagement.py` (Layer 1): `source` field, `adopt`, `assign_desk`,
  `room_requests`, `unlinked_answer`, adoption watermark file beside the store.
- `lib/set_orch/fleet/takeover.py` (Layer 1): unclaimed engagements — live desk assignment, grace,
  start with an "unclaimed" takeover.
- `lib/set_orch/fleet/mandate_delivery.py`: the takeover block for an unclaimed request.
- `lib/set_orch/api/fleet_mandate.py`: `takeover_round` adopts before it refreshes.
- No bus change, no stored request text; the engagement stays a pointer.
