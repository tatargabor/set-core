## 1. Adoption (Layer 1 core)

- [x] 1.1 CORE — `engagement.py`: `source` field (`ask` | `room`), `adopt(room, ts, asker, project, kind, sent_at)` idempotent on room+ts, `assign_desk` (open → open, no handover). [REQ: a-request-posted-straight-into-a-relation-room-is-adopted]
- [x] 1.2 CORE — `room_requests(store_root, since, now)`: relation rooms only, heading lines only, project-addressed or unaddressed, 90 s ≤ age ≤ 24 h, newer than the watermark; files not written since the later bound skipped. Watermark file beside the store, created on first use. [REQ: a-request-posted-straight-into-a-relation-room-is-adopted]
- [x] 1.3 CORE — `unlinked_answer` + `refresh` closes a `room` engagement on a linked reply or the addressed project's first unlinked ANSWER after it; `ask` engagements unchanged. [REQ: an-adopted-request-is-answered-by-a-linked-or-an-unlinked-answer]
- [x] 1.4 TEST — Unit tests for 1.1-1.3 on a fake bus directory; each fails without its code. [REQ: a-request-posted-straight-into-a-relation-room-is-adopted]

## 2. Unclaimed engagements (Layer 1 core)

- [x] 2.1 CORE — `TakeoverWatch`: an engagement with no desk gets the project's live desk row (assigned, no handover); with none, nothing before one stall bound, then a desk started with an unclaimed takeover and assigned. [REQ: an-unclaimed-adopted-request-gets-a-desk]
- [x] 2.2 CORE — `mandate_delivery._takeover_lines`: a takeover with no predecessor says nobody picked the request up. [REQ: an-unclaimed-adopted-request-gets-a-desk]
- [x] 2.3 CORE — `api/fleet_mandate.takeover_round` adopts before it refreshes; logs counts, never text. [REQ: a-request-posted-straight-into-a-relation-room-is-adopted]
- [x] 2.5 CORE — `engagement.seen_by` (bus read cursors) — no desk is started for a request a live session of the project has read; `assign_desk` also records the desk of an engagement answered meanwhile (M3/M4). Both mutation-checked. [REQ: an-unclaimed-adopted-request-gets-a-desk]
- [x] 2.4 TEST — Unit tests for 2.1-2.2. [REQ: an-unclaimed-adopted-request-gets-a-desk]

## 3. Live verification

- [x] 3.1 LIVE — Restart set-web after the commit; the watermark file exists and nothing older was adopted. (15:25:31 restart; watermark 15:26:47; 0 `room` engagements of 33.) [REQ: a-request-posted-straight-into-a-relation-room-is-adopted]
- [x] 3.2 LIVE — An unaddressed REQUEST posted with `sac send` into a relation room is adopted within two rounds and closed by its answer. Record in `measurements.md`. (M3: posted 18:28:27, adopted 18:30:53, desk started 18:33:56, its linked ANSWER 18:34:08, `answered` 18:34:09.) [REQ: an-adopted-request-is-answered-by-a-linked-or-an-unlinked-answer]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN an unaddressed REQUEST by A sits in `dm-A--B` for two minutes after adoption was on THEN an open `room` engagement for B with its room and ts exists [REQ: a-request-posted-straight-into-a-relation-room-is-adopted, scenario: an-unaddressed-request-in-a-relation-room]
- [x] AC-2: WHEN the room+ts already has an engagement THEN no second one opens [REQ: a-request-posted-straight-into-a-relation-room-is-adopted, scenario: already-tracked]
- [x] AC-3: WHEN the REQUEST is addressed to `B#<id>` THEN it is not adopted [REQ: a-request-posted-straight-into-a-relation-room-is-adopted, scenario: addressed-to-one-session]
- [x] AC-4: WHEN the entry predates the watermark THEN it is not adopted [REQ: a-request-posted-straight-into-a-relation-room-is-adopted, scenario: older-than-adoption]
- [x] AC-5: WHEN B posts an unlinked ANSWER after an adopted request THEN it is answered [REQ: an-adopted-request-is-answered-by-a-linked-or-an-unlinked-answer, scenario: unlinked-answer]
- [x] AC-6: WHEN B's only later entry is an ANSWER linked elsewhere THEN it stays open [REQ: an-adopted-request-is-answered-by-a-linked-or-an-unlinked-answer, scenario: an-answer-to-something-else]
- [x] AC-7: WHEN B has a live desk THEN the engagement names it with 0 handovers [REQ: an-unclaimed-adopted-request-gets-a-desk, scenario: a-live-desk-exists]
- [x] AC-8: WHEN B has no desk and the request is younger than the stall bound THEN no desk starts [REQ: an-unclaimed-adopted-request-gets-a-desk, scenario: no-desk-within-the-grace]
- [x] AC-10: WHEN B has no desk, the request is past the grace, and a live session of B has read it THEN no desk starts [REQ: an-unclaimed-adopted-request-gets-a-desk, scenario: read-by-a-live-session]
- [x] AC-9: WHEN B has no desk and the request is older than the stall bound THEN a desk starts with a predecessor-less takeover, is named, 0 handovers [REQ: an-unclaimed-adopted-request-gets-a-desk, scenario: no-desk-past-the-grace]
