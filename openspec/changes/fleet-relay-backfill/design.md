## Context

The relay's carrier is a `PreToolUse` hook on `AskUserQuestion`. While the relay switch is off,
the hook returns at once and the question opens in the terminal's own dialog. Turning the switch
on later changes nothing for that question, because its hook has already returned. The same gap
exists one layer down: with the relay on and automatic answers off, a question is posted and
waits, and turning automatic answers on does not start a decider for it, because the decider is
started only by the outbound at hand-over time.

Measured on the live machine the day this was asked for (owner's report): the relay switch
was off from 13:04:41 to 13:42:09. At 13:5x three fleet-held sessions had an open
`AskUserQuestion` (runtime status `waiting`, a `tool_use` with no `tool_result` in the
transcript) and no relay waiting record.

## Goals / Non-Goals

**Goals:**
- A switch-on reaches every question open at that moment in a fleet-held terminal.
- An answer to such a question arrives in the agent like a typed answer, never into a session
  that has moved on.
- What cannot be reached is reported, not silently skipped.

**Non-Goals:**
- A watcher that keeps scanning while the switch stays on. The hook covers new questions; this
  change covers the moment the switch changes.
- Plain terminals outside the fleet (the same limit B-214 has).
- Any new panel element.

## Decisions

**D1 — The trigger is the switch-on, plus a by-hand command.** Both toggles in
`api/fleet.py` start the pull-in after a successful turn-on and return its report in their
response. `set-relay-backfill` runs the same function. Alternative: a periodic scan. Rejected,
because a question the operator sent "to terminal" would be pulled back every round. A switch-on
is a fresh statement ("I am away now"), so it re-pulls such questions; a timer would not know
that.

**D2 — One carrier process per pulled-in question, outside set-web's cgroup.** A pulled-in
question waits up to the relay's timeout (55 min). A thread inside set-web would die with every
service restart, and a plain `Popen` child too, because systemd stops the whole control group.
The carrier is started with `systemd-run --user --collect` when that is available, and as a
detached `Popen` (new session) otherwise. The carrier is `set-relay-backfill --carry` with the
call on stdin.

**D3 — The answer is delivered through the terminal: Esc, one line, Enter.** The hook that
would have returned the answer is gone, so the only way in is the terminal the fleet holds. The
sequence and the pauses are the takeover interrupt's (`takeover.owner_interrupt`, measured
there). Esc closes the open dialog, and the line then starts the next turn carrying the answers.
Alternative: drive the dialog's own option list with arrow keys and digits. Rejected: it depends
on the dialog's layout, multi-select and multi-question tabs, and "Other" text entry, and a
wrong keypress answers the wrong option. One line in words cannot be misread by the agent.

**D4 — The pulled-in question looks exactly like a hooked one to everything downstream.** The
call id is `call_id(session_id, tool_use_id)`, the same one the hook would have made. The
envelope comes from `build_envelope` on the call's own `tool_input`, and the waiting record has
the hook's shape plus `backfill: true`, `tool_use_id` and the terminal `label`. The bridge, the
fleet panel, the decider's `_record_live`, "to terminal", teach and the send button therefore
need no change.

**D5 — The decider gains a decide-only mode for questions already posted.** With
`SET_RELAY_NO_FORWARD=1` in its relay variables, the worker decides, writes its pending record
and the decision log, and writes an allowed answer after the window. It does not forward, and
it does not release a question it cannot answer (the operator already has it). This is the
second half of the auto-answer switch-on: each relay waiting record of kind `ask` with no
pending decider record gets one such worker. Its envelope is rebuilt from the transcript's open
call whose `call_id` equals the record's id. A record whose call cannot be found that way is
left alone and counted.

**D6 — Finding the open questions.** Fleet-held sessions come from the owner daemon's
`list_agents()` (label → agent pid), the session record `~/.claude/sessions/<pid>.json`
(→ session id) and the transcript (→ open `AskUserQuestion` calls with their input, sidechain
entries skipped). Sessions outside the fleet come from `discovery.discover_agents()`; an open
question there is reported as `not-fleet-held` and left alone.

**D7 — Staleness is re-checked at the last moment.** Each poll and once more after an answer
arrives, the carrier checks: is the `tool_use` still without a `tool_result`, is the release
marker unset, is the switch on, is the waiting record still its own, is the label still live.
Only then does it remove the record and type.

## Risks / Trade-offs

- [Esc in the question dialog behaves differently in some runtime version] → measured live
  before shipping (a task), on a scratch fleet agent, with the transcript read afterwards.
- [The operator is at that terminal and starts answering in the dialog while the channel answer
  arrives] → the last-moment transcript check catches a submitted answer. A half-typed one is
  lost to the Esc. That is accepted: the switch-on said the operator is away.
- [A carrier outlives a restarted owner daemon or a closed terminal] → it checks the label each
  poll and ends when it is gone.
- [A multi-question call is long on one line] → each question is shortened to its header (or its
  first 60 characters), and the answers stay whole.

## Migration Plan

No data migration. Ships with set-web's restart. Rollback is reverting the commit: the toggles
then change only the switch again, as before.

## Open Questions

None.
