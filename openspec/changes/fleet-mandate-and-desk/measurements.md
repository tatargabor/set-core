# Measurements — fleet-mandate-and-desk

Every figure here was produced by a command run on 2026-11-23 against runtime 2.1.330. Each
entry says what was run, what came back, and what it does **not** show.

## M1 — a `SessionStart` hook passed as a `--settings` JSON string (tasks 1.1, 1.2)

**Setup.** A throwaway git project with three tracked files. An agent started in a terminal
multiplexer pane with the owner's argv plus the additions under test:

```
SET_FLEET_MANDATE=<id> SET_FLEET_LABEL=<label> \
  claude --dangerously-skip-permissions --settings '<json>' '<opening line>'
```

where `<json>` is `{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"<hook>"}]}]}}`.
The hook appends its stdin and the two variables to a log and prints
`{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"… token …"}}`.

**Result — the hook fired on all four sources, with the variables visible each time:**

| source | session id | mandate variable seen by the hook |
|---|---|---|
| `startup` | first | yes |
| `clear` | second (rotated) | yes |
| `compact` | second (unchanged) | yes |
| `resume` | second | yes |

The hook's stdin carries `cwd`, `hook_event_name`, `model`, `scratchpad_dir`, `session_id`,
`source`, `transcript_path`.

**The context reaches the agent.** Asked for the planted token, the agent answered it after the
start, after the clear and after the compaction (3 of 3).

**What this does not show.** After the compaction the token could have come from the summary
rather than from the hook; the hook firing with `source: compact` is the evidence for delivery,
the answer is not. The run used the smallest model; the carrier does not depend on the model,
but that is a reason, not a measurement.

## M2 — the collision case and the project tree (task 1.3)

The probe project declared its **own** `SessionStart` hook in `.claude/settings.json`. It fired
beside the framework's on every one of the four sources — same timestamps, same session ids. So
hook lists are additive for `SessionStart`, as they were measured to be for `UserPromptSubmit`.

Tree hashes before and after (every file outside `.git`): the three tracked files are
byte-identical. **Two files appeared**, `.set/handoff/.context-tokens-<session>`, one per
session id. They are written by the machine's own global status line script (it contains that
file name; the carrier supplies no status line). So the carrier added and changed nothing, and
the statement "the tree is byte-identical" is true of the carrier and **false of the machine as
configured** — a test for this must compare against a run without the carrier, not against an
empty expectation.

## M3 — the opening line (task 1.4)

The positional prompt started a first turn with nobody typing, and the reply contained both
the fixed word the prompt asked for and the token from the session-start context. So the two
arrive together and the agent can act on the mandate in its first turn.

**Limit.** Run under a multiplexer pane, not under the owner's pty and scope — the owner cannot
take these additions until task 3.1 exists. Task 9.1 exercises the real path.

**By-catch that changes the design.** In a folder the runtime has never been trusted in, the
start stops at a trust prompt and waits for a key. An unattended desk start in such a project
would sit there, unreachable. Resolution therefore needs a refusal for "never trusted here",
checked before the start (added to the `project-desk` spec and task 4.3).

## M4 — time until a started agent has a bus seat (task 1.5)

Ten agents started one after another through the fleet's start route in a bus-enrolled
project, each polled once a second through the fleet inventory, then stopped.

| | seconds |
|---|---|
| session id visible | 2.1 – 2.5 |
| bus seat joined to the agent | 6.9, 6.9, 8.3, 8.3, 8.5, 8.5, 8.6, 8.6, 8.7, 8.8 |

10 of 10 obtained a seat with no turn taken. **The readiness bound is set to 60 seconds** —
about seven times the slowest observation, because the poll and the inventory round are part of
the figure and a loaded machine will be slower.

All ten were stopped; none was left in the inventory, as a scope unit, or as a pane.

## M5 — what a bus send returns, and what a linked reply looks like (task 1.6)

In a throwaway bus store (two fake seats, one room, no real text):

- `send` prints one JSON object with `ts`, `room`, `from`, `type`, `to`, `wakes`, `path`.
- Entries are appended to `channels/<room>/<seat>.md`; **the sender is the file name**, not a
  field of the heading.
- Headings, verbatim from the writer:

```
## <ts> — REQUEST → <addressee>
## <ts> — ANSWER (re: <request ts>)
## <ts> — FACT
```

A linked reply carries `(re: <ts>)` and may carry no addressee clause at all. So closure is:
a heading with `(re: <request ts>)` in a file whose name is a seat of the addressed project, in
the request's room. The fixtures for task 5.2 are built from these three lines.

## M6 — deciding that a project is on the bus (task 1.7)

`sac doctor --json` returns, per project, `hooks` (which hooks are wired and from where),
`live`, `rooms`, `path` and a `verdict`. Over the registered projects on this machine: 54 have a
session-start hook wired, **27 do not** (verdict `off`). So "not on the bus" is a third of the
projects, not an edge case.

Decision: enrolled means the `hooks` object has a `session-start` entry. Fail direction of the
alternatives: reading the project's settings file ourselves would duplicate the bus's own
resolution and miss a hook wired through a plugin; the `verdict` field also turns `warn` for
reasons that do not prevent a seat. When the doctor cannot be run, enrolment is **unmeasured**
and the request is refused as such, rather than started on a guess.

## M7 — which room a seat-addressed request lands in (task 5.5)

In a throwaway bus store with two projects that also shared an unrelated room: a send from
one project addressed to a **seat** of the other, with no room named, went to the project
pair room (`dm-<a>--<b>`) — the bus opens it on its own — and woke exactly that seat. The same
happened once the pair room already existed, and with the room named explicitly. The send's
JSON carried `room` and `ts` each time.

So `set-fleet-ask` names no room: the request lands in one stable room per pair of projects,
however many desks come and go, and the engagement's pointer is read from the send's answer.
The bus's machine-readable agent list carries each seat's FULL session id, which is how the
command finds the asker's own seat.

## M8 — end to end on the live services (task 9.1), 2026-11-23

After the agent-owner restart (20:51, `features` carry `mandate`). Asker: a set-core session's
own seat. Target: an enrolled framework project with no live session (`sac doctor --json`:
`session-start` hook present, `live: None`).

```
21:24:11  set-fleet-ask --question --subject "9.1 live check" --from <set-core seat> <project> "<one-line question>"
          → "e-0f4b94f72027: sent to <project>'s desk <project>#4415656a (started for this request).
             The reply arrives on the bus, linked to your request."
21:24:21  the QUESTION lands in the project pair room `dm-<project>--set-core`, addressed to the desk seat
21:24:25  GET /api/fleet/map → relations: one `engagement` (state open, age 14 s, subject "9.1 live check")
          and one `started` (is_claim true) from the asker to the desk; the desk carries kind `desk`
21:24:36  ANSWER → asker (re: 21:24:21.797) — the reply is LINKED; content correct against the repo
21:24:41  the asker's `sac wait --once` woke on that ANSWER
21:25:08  set-fleet-ask --list → `e-0f4b94f72027  answered  …  57 s  9.1 live check`
```

Time from the command to the linked answer: 25 s, of which ~10 s was the desk getting a seat.

**What was NOT observed, and why.** The desk did not go quiet after answering: the project's
pair room held three older REQUESTs addressed to the PROJECT (from an earlier set-core session,
left unread because no session of that project was running), and the desk took them up as its
next work. That is the desk doing its job — a request addressed to a project is the desk's —
but it means "the desk stops after the bound" (default quiet bound: 30 minutes, `desk.DEFAULT_QUIET_MINUTES`) could not be seen in
this run. It is observed when the desk next goes quiet; until then 9.1 stays open on that one
point.

**A side finding during the run.** set-web was restarted by another session at 21:24:38 and
answered nothing until 21:25:04: application startup waits on a 15 s Discord connect timeout
(`[SET] Discord bot timeout — not connected`, then `Application startup complete`). The bus
path was unaffected — the answer arrived while the dashboard was down — but every fleet
command that reads the dashboard (`set-fleet-ask --list`, the map) failed with connection
refused for ~26 s.
