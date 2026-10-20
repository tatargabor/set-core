## Context

The fleet screen measures an agent's state from its **session log**: an outstanding `tool_use`
means working, an outstanding question tool means asking, and anything else is `quiet` — a word
chosen precisely because the log cannot tell *finished its turn* from *stopped in front of a
person*. That distinction was left to the runtime's record, and to a model pass over the last
utterance.

The record was distrusted for a good reason. On 2026-08-18 its `status` field was measured
across 23 live sessions with a **median age of 11 hours**, and `state.py` carries a comment
forbidding its use as the state source. That decision was correct for what was measured.

**It is no longer correct, and the difference is a runtime version.** Everything below was
measured on 2026-08-28 against runtime **2.1.251**.

### The measurements this design rests on

| what | how it was measured | result |
|---|---|---|
| The status vocabulary | string extraction from the runtime binary: `["busy","shell","idle","waiting"]`, validated by `Ke()` | four values, not two |
| What `shell` means | the binary's own expression: `base === "idle" && hasRunningBackgroundBash ? "shell" : base`, where the predicate is `Object.values(tasks).some(t => t.type === "local_bash" && !done(t.status))` | *prompt free, background command running* |
| When the record is written | the binary's effect depends on `[status, waitingFor]` only | on CHANGE, so the stamp is the state's age |
| Stamp accuracy | 10 live sessions with a log: `statusUpdatedAt` vs the last log ENTRY timestamp | 10/10 equal to the second |
| Log mtime accuracy | the same 10 sessions: mtime vs the newest entry | 2/10 off by 90 min and 58 min — the file is rewritten without new entries |
| Transition latency | a pty probe driving a real interactive session | `idle→busy` 0.6 s; `busy→shell` on backgrounding; `shell→busy→idle` at turn end; every stamp within 0.2 s |
| Headless runs | `claude -p` observed while it ran | `entrypoint: "sdk-cli"`, **no `status` key at all** |
| Background job sessions | this session's own record | `kind: "bg"`, `entrypoint: "cli"`, status present and correct |

The direction of the old finding matters more than its number: an `idle` stamp that is hours old
was read as *stale*, when it is in fact *the length of the wait*. That misreading is what made
the field look useless, and it is the same class as measuring a proxy instead of the thing.

## Goals / Non-Goals

**Goals:**

- Answer, per agent and without opening a tile: is it working, is a background command running,
  or has it been waiting for a person — and for how long.
- Escalate that wait visually at 15 s and 3 min, on the project row and on the group header.
- Say whether typing at that session now would be acted on or queued.

**Non-Goals:**

- Judging whether a quiet turn *asked* something. That is the model pass, unchanged.
- Ordering the attention queue, the countdown, the typing guard — `fleet-pm-mode` owns those.
- Replacing the log as the source of *working*. The log stays; the record composes onto it.
- Waking, notifying or writing into a session.

## Decisions

### D1 — The record's status refines the state; the log still decides *working*

`read_state` keeps its structure. What changes is `_apply_declared_wait`, which today only
promotes `quiet → waiting` when the record says `waiting`. It becomes a full mapping of the four
values, and it yields two new fields rather than overwriting `state` in more cases.

*Alternative rejected:* make the record the primary source and drop the log scan. It would lose
`asking` (which tool is open, and for how long) — a strictly more specific fact — and it would
make a runtime version bump able to blank the whole screen. Composition degrades; replacement
fails.

### D2 — A new axis (`attention`) rather than new `state` values

`state` keeps its five values (`working`, `quiet`, `asking`, `waiting`, `unknown`) and their
tallies. A parallel field `attention` carries `working | background | input | prompt | unmeasured`.

*Alternative rejected:* splitting `quiet` into `quiet-idle` and `quiet-shell`. Every consumer of
`state` — the tally, the header, the PM queue's candidate selection, the tests — would have to
learn two new names to keep working, and the ones that were not updated would fall into
`unbucketed` rather than failing loudly. A new axis leaves every existing reader correct.

### D3 — The wait duration comes from `statusUpdatedAt`, and `last_movement_age` stays

`input_wait_seconds` is `now - statusUpdatedAt` when the class is `input` or `prompt`, and
`None` otherwise. The existing `last_movement_seconds` (log mtime) is left alone: it answers
"when did this file last move", which is a different question and is now known to over-report.

### D4 — One threshold table, in Python, mirrored by a generated-from-constant in TS

`INPUT_WAIT_AMBER_SECONDS = 15` and `INPUT_WAIT_RED_SECONDS = 180` live in
`lib/set_orch/fleet/state.py`, are carried in the API envelope (`thresholds`), and the web layer
resolves tone from the envelope when present, falling back to the same two literals. A test
asserts the two sides agree, so a drift fails a test rather than colouring two screens
differently.

*Alternative rejected:* resolving the tone server-side only. The wait grows between polls; a
tone computed at fetch time would go stale on screen for as long as the poll interval, which on
a 3-minute threshold is exactly where it matters. So the server carries the numbers, the client
does the arithmetic every render.

### D5 — Amber is taken back from `unknown`

`unknown` becomes a **dashed hollow** marker in `fg-muted`; amber becomes the input-wait mark.
This is the one change here that touches something already shipped, and it is deliberate: the
user asked for green/amber/red on this axis, and a hue carrying two meanings is worse than
either.

*Alternative rejected:* colouring the input wait sky-blue → amber → red. Sky already means
"waiting for an answer" on the tile, so the first band would be invisible against the state it
is escalating.

### D6 — `prompt` (permission dialog) enters at the amber band immediately

A session stopped at a permission prompt is blocked on a person by construction, so it does not
need 15 s of evidence. It uses the same red threshold, so a forgotten prompt still turns red.

## Risks / Trade-offs

- **A human standing at the keyboard typing an answer still reads as "waiting 3 minutes".** The
  status tracks the loop, not the person. → Named in the tile's tooltip; the PM queue's typing
  window already handles the case where the reader is here, and this axis deliberately describes
  the session rather than guessing at the human.
- **A runtime version that renames a status value would fall through.** → The mapping has an
  explicit final branch: an unrecognised value is `unmeasured` **and is logged with the value's
  name**, never silently mapped onto a neighbour. A test holds a fabricated status and asserts
  it lands in `unmeasured`.
- **`shell` only tracks background *bash*.** A running subagent or workflow shows as `busy`, not
  `shell`, because the runtime folds those into the base status. → That is the honest reading
  either way (`busy` means something is running), and the class distinction the user asked for —
  *is a background task running?* — is preserved.
- **Reversing a documented decision invites a session to "restore" it.** → The comment block in
  `state.py` that forbids the status field is rewritten in place with the new measurement and
  its date, rather than deleted, so the next reader meets the correction and not a silent
  contradiction.
- **The 90-minute mtime divergence suggests other consumers of `last_movement_age` over-report
  movement too.** → Out of scope here; recorded in the bug register rather than fixed inside
  this change.

## Migration Plan

Additive. New fields default to `None` / `unmeasured`, so a stale web bundle keeps rendering the
current screen and a new bundle against an old API renders no escalation rather than a wrong
one. No data, no migration, nothing persisted.

## Open Questions

- Should a `prompt` (permission dialog) wait be *louder* than a plain input wait at the same
  age — a distinct mark rather than the same amber? Deferred: it can be added without changing
  the measurement, and one visual weight per meaning argues for seeing the two-band version on
  a real screen first.
