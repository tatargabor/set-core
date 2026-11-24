# Measurements — fleet-room-request-adoption

## M0 — the gap (2026-11-24, before the change)

Three days of relation rooms (`dm-<a>--<b>`), heading lines only: 110 cross-project REQUEST/QUESTION
entries, 24 tracked by an engagement. Of the 66 untracked ones not addressed to one session:
21 linked reply, 36 unlinked ANSWER by the addressed project, 1 other entry, 8 nothing.
The case that surfaced it: `dm-set-claude-handoff--set-core` 14:07:11 (an unaddressed REQUEST);
no engagement at 14:08; answered with a link at 14:11:54 by the live desk — handled, but unwatched.

## M1 — switched on (3.1)

set-web restarted 15:25:31; the first round wrote the watermark at 15:26:47
(`~/.local/state/set-core/fleet-engagement-adopt.json`, log `adoption switched on`). The engagement
view listed 0 `room` engagements of 33: nothing posted before the switch was adopted.

## M2 — replay on the real bus (read-only, temporary store)

`adopt_room_requests(since=now-24h)` into a scratch store, then `refresh`: 14 adopted, 7 answered
(linked or unlinked), 7 open, 0 unreadable. The 7 open ones are the requests the M0 count found
with no answer after them — the parse and the closure agree with the independent measurement.

## M3 — end to end, live (3.2)

No qualifying request arrived in the first three hours (15:26-18:27): three relation-room requests,
two addressed to one session (both already asked through `set-fleet-ask`), one addressed to
`owner` — none adoptable, as designed. Active test: set-core posted an unaddressed REQUEST into
`dm-set-claude-handoff--set-core` asking for one ANSWER and no work.

| time | event |
|---|---|
| 18:28:27 | REQUEST posted |
| 18:30:53 | adopted (`e-76748388de6d`, 146 s: the 90 s floor plus a round) |
| 18:33:56 | `-> start (unclaimed for 328 s; project has no live desk)` |
| 18:34:07 | the started desk's FACT: "… is now held by …" (the unclaimed wording) |
| 18:34:08 | its ANSWER, linked to the request |
| 18:34:09 | `open -> answered`; `assignment ignored` — the record closed before the round recorded the desk |

The project's live ordinary session had not read the request (its cursor for the asker in that
room was empty), so the start was the right call. The record no longer naming the desk that
answered is fixed (task 2.5).

## M4 — answer latency of room requests (why a read check, not a longer grace)

Seven days of relation rooms, project-addressed or unaddressed requests with a linked reply or an
unlinked ANSWER by the addressed project: n=108, median 104 min, p75 1207 min. Answered after
5 min: 81; after 10: 76; after 15: 69; after 20: 66; after 30: 64. No grace bound separates a
request somebody is working on from one nobody saw; the bus read cursor does.
