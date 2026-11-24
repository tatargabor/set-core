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
