## Why

A request one agent sends another project can stop for good, and nothing moves it on. On
2026-11-24 the relation map showed two such requests at once, both measured:

- **A request failed `desk-not-ready` while a desk was running.** A fleet listing that did not
  see the live `set-core` desk ended its mandate (08:12:20, reason `ended`); the agent itself ran
  on until 08:27 and kept its label. The next request (08:21:56) could neither start a desk (the
  owner refused the held label) nor find one (the running agent no longer carried an open desk
  mandate), and failed after 60 s.
- **A request sat open for three hours behind a hung desk.** A consumer project's desk issued
  a Bash call at 08:10:30 bounded at 580 s. Its process was gone, the result never came back, and
  the session showed "working" with no movement until 11:07. Its asker — another consumer
  project's desk — had meanwhile been stopped by the quiet sweep (08:17) although it was itself
  waiting on this answer.

The owner's decision (2026-11-24): work must not stop on such a request — the fleet decides on
its own to take it over — while staying token-efficient, and the bus must say the request
changed hands. A desk that is genuinely working is not duplicated.

## What Changes

- **A takeover watch over open engagements.** Each open request's desk is measured on a short
  round: is it live, is it moving (transcript movement), is it working in the background
  (CPU of its process tree outside the agent's own process). A desk with no movement and no
  background work for the stall bound (5 min), or a request past the hard ceiling (30 min,
  the existing waiting bound), is escalated.
- **The ladder is interrupt first, replace second.** Step 1 interrupts the desk's turn and types
  one line naming the open request — the session keeps its warm context, the cheapest recovery
  (verified live on 2026-11-24: the hung desk took a new turn within seconds). Step 2, when the
  request is still unanswered and the desk still stalled one stall bound later, or at once when
  the desk is gone: stop it and start a fresh desk that **takes over** the request.
- **A takeover carries the predecessor's state.** The new desk's mandate names the request (room,
  timestamp, asker), the predecessor seat and session, and tells it to read where the work got —
  the end of that transcript and the project's OpenSpec change state — and continue, not restart.
  Its first act is an unaddressed FACT in the request's room: the request moved from seat A to
  seat B. Unaddressed, so it wakes nobody.
- **A bound on takeovers.** At most two per request; after that the request stays open and
  waiting on the map, so a request that kills every desk does not burn tokens forever.
- **Three defects fixed:** a mandate is ended only when its agent's unit is measured gone; a held
  desk label whose mandate was ended while its unit runs is re-adopted as the desk; the quiet
  sweep keeps a desk that has its own request open.

## Capabilities

### New Capabilities
- `engagement-takeover`: keeping a cross-project request moving — stall measurement, the
  interrupt/replace ladder, the takeover mandate and bus notice, the takeover bound, and the
  liveness guarantees (mandate ending, label re-adoption, asker kept alive) it depends on.

### Modified Capabilities
- None in `openspec/specs/`. The desk, engagement and mandate capabilities this builds on are
  still in the open change `fleet-mandate-and-desk`; this change adds to them without editing
  that change's requirements.

## Impact

- `lib/set_orch/fleet/takeover.py` (new, Layer 1): the stall decision and the ladder, every
  dependency injected.
- `lib/set_orch/fleet/engagement.py`: takeover fields on the record (`nudged_at`, `handovers`).
- `lib/set_orch/fleet/mandate.py`: `end_missing` takes a unit-liveness measurement; a takeover
  field on the mandate; re-opening an ended desk mandate.
- `lib/set_orch/fleet/mandate_delivery.py`: the takeover block in the desk's context.
- `lib/set_orch/fleet/desk.py`: label re-adoption; the sweep keeps a desk with its own open request.
- `lib/set_orch/api/fleet_mandate.py`: the takeover round in the service, its loop, and the sweep fix.
- `lib/set_orch/api/fleet.py`: the listing's mandate settling passes unit liveness.
- Local config: `fleet_takeover_stall_minutes`, `fleet_takeover_max`, `fleet_takeover_cpu_percent`.
- No change inside `set-agent-comm`; no new transport.
