# fleet-relay-backfill — measurements

## M1 — the cause, on the live machine (2026-11-24)

`journalctl --user -u set-web`: `question_relay.enabled True -> False` at 13:04:41, `False -> True`
at 13:42:09. At 13:5x a scan of the owner's terminals (`list_agents` → session record →
transcript) found three sessions with an `AskUserQuestion` `tool_use` and no `tool_result`,
runtime status `waiting`, and no relay waiting record. Nothing had looked at them since the
switch came back on.

## M2 — a test reached the live machine (defect found while building this, fixed before shipping)

At 14:11:15 the unit suite ran `test_api_toggle_and_release`, which turns the relay on in a
temporary config. The switch-on ran the real pull-in with the default world: the real owner's
terminals, the real transcripts. Three carriers started under `systemd-run`, and a transient
unit starts in the USER MANAGER's environment, so `SET_QUESTION_RELAY_DIR` did not reach them
and they handed the three real questions to the real outbound
(`journalctl --user`: `Started …set-relay-backfill --carry --job /tmp/pytest-of-…`;
`relay.log` 14:11:15 "pulled in" ×3, 14:11:16 "waiting record replaced or removed; nothing typed" ×3).
`auto-answer.log` shows three "worker started" and no decision after: the workers lived in the
carriers' units and were killed with them (default `KillMode=control-group`), so nothing was
forwarded to the channel and nothing was typed. The records were removed by the running
set-web, whose old `_CARRIER_MARKS` did not know the carrier (the B-192 shape).

Fixed: `tests/unit/conftest.py` makes the module's reach into the machine empty and the real
launch refuse, for every unit test; the carrier gets the caller's state/config environment
through `--setenv`; `--property=KillMode=process` keeps the decider alive past the carrier.
After the fix the same suite run (361 tests) left `relay.log` unchanged and started no unit.

## M3 — on runtime 2.1.331 an open question is NOT in the transcript when no hook ran

A scratch fleet agent (`--settings '{"disableAllHooks":true}'`, haiku) asked one
`AskUserQuestion`; its dialog was on screen (owner `tail`) and its session record said
`status: waiting, waitingFor: input needed`. The transcript held **no `assistant` entry at all**
for 3+ minutes (mtime unchanged since the ask). On the same runtime, a session whose relay hook
had run (`set-core-opensource`) had the open `tool_use` in its transcript. So a transcript scan
alone misses exactly the case it is for. Consequence for the design (D6 revised): the hook
records the call when the relay is off (a "parked" record), and the pull-in reads those first;
the transcript scan stays as the fallback. The carrier's "still open" check reads only for a
`tool_result` with the call's id, never for the `tool_use`'s presence.

## M4 — Esc, one line, Enter on an open question dialog (task 4.1)

On that scratch agent, `takeover.owner_interrupt(label, answer_line(...))` at 14:15. The
transcript afterwards, in order:

- `assistant tool_use AskUserQuestion toolu_013i…` — written only now, at the resolution
- `user tool_result … is_error: true` "The user doesn't want to proceed with this tool use…"
- `user text [Request interrupted by user for tool use]`
- `user` the typed line: `[fleet] Your question was answered on the relay channel … Q1 “Banner”: ORANGE — continue with this answer.`
- `assistant text GOT: ORANGE`

Esc closes the dialog as a rejected call, the line becomes the next turn, and the agent acts on
the answer. Task 4.1 done.

## M5 — the whole path on a scratch fleet agent, real carrier launch (task 4.2)

An isolated world so nothing reached the operator's channel or a real session: the agent ran
with `SET_CONFIG_DIR` pointing at a config with the relay OFF and its own
`SET_QUESTION_RELAY_DIR`, and only the `AskUserQuestion` hook wired (`--setting-sources user
--settings …`). The pull-in ran with a config where the relay is ON and the outbound is `true`.

- 14:19 the agent asked; the hook parked it (`parked/<session>.json`, `-rw-------`). On this
  runtime the transcript did hold the open `tool_use` this time (2 `assistant` entries) — the
  hook HAD run, which matches M3's difference.
- 14:19:21 the pull-in (filtered to the scratch label) reported `1 pulled in`; the carrier ran as
  `set-relay-backfill-337a857c-….service` under `systemd-run`, its waiting record landed in the
  SCRATCH state dir (so `--setenv` carried it), and the park record was gone.
- 14:19:35 an answer delivered as the panel does (`deliver_answer(..., "ORANGE")`): relay log
  "answered on the channel; typed into scratch-backfill2"; the unit ended; the waiting dir empty.
- Transcript: `tool_use AskUserQuestion` → `tool_result is_error` → `[Request interrupted…]` →
  the typed `[fleet] … Q1 “Banner”: ORANGE …` → `assistant: GOT: ORANGE`.

Task 4.2 done. The decider-written answer (AC-5) goes through the same answer store; a unit test
drives the carrier with the worker's own `_write_answer`.
